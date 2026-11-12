"""Minimal read-only IMAP + MIME utilities for campus-video.

Adapted from the MIT-licensed campus-radar project. This module keeps the skill
self-contained: no campus-radar installation is required for fetching mail.
"""
from __future__ import annotations

import hashlib
import imaplib
import re
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # Windows without tzdata
    LOCAL_TZ = timezone(timedelta(hours=8))

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
URL_RE = re.compile(r"https?://[^\s<>\"'\u3000]+", re.IGNORECASE)
TRAILING_URL_CHARS = "。，、；;,.!?)）]】}>'\""
imaplib.Commands["ID"] = ("AUTH", "SELECTED")


def imap_date(value: datetime) -> str:
    return f"{value.day:02d}-{MONTHS[value.month - 1]}-{value.year}"


class MailboxError(Exception):
    """A safe, user-facing mailbox connection error."""


@dataclass(frozen=True)
class MailAccount:
    provider: str
    email: str
    username: str
    password: str
    host: str
    port: int
    folder: str = "INBOX"


@dataclass(frozen=True)
class SearchResult:
    uids: list[int]
    uidvalidity: str | None
    top_uid: int


@dataclass(frozen=True)
class EmailLink:
    url: str
    text: str = ""


@dataclass
class ParsedEmail:
    subject: str
    sender_name: str
    sender_email: str
    received_at: datetime
    body_text: str
    html_text: str
    links: list[EmailLink] = field(default_factory=list)
    message_id: str = ""
    list_unsubscribe: str = ""
    precedence: str = ""
    reply_to: str = ""

    @property
    def from_line(self) -> str:
        if self.sender_name and self.sender_email:
            return f"{self.sender_name} <{self.sender_email}>"
        return self.sender_name or self.sender_email


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "") + '"'


def _parse_uid_search_response(data: list[object] | tuple[object, ...] | None) -> list[int]:
    found: set[int] = set()
    for chunk in data or []:
        if isinstance(chunk, bytes):
            tokens = chunk.split()
        elif isinstance(chunk, str):
            tokens = chunk.split()
        else:
            continue
        for token in tokens:
            try:
                found.add(int(token))
            except (TypeError, ValueError):
                continue
    return sorted(found)


def _humanize_error(exc: Exception, provider: str) -> str:
    raw = str(exc)
    lowered = raw.lower()
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in lowered:
        return "连接邮箱超时，请检查网络，或稍后重试。"
    if isinstance(exc, socket.gaierror) or "name or service not known" in lowered:
        return "找不到 IMAP 服务器，请检查服务器地址和网络。"
    if "certificate" in lowered or isinstance(exc, ssl.SSLError):
        return "IMAP 服务器的 TLS 证书验证失败，请确认服务器地址是否正确。"
    if any(cue in lowered for cue in ("authenticationfailed", "authentication failed", "invalid credentials", "login fail", "login failed", "auth failed", "unsafe login")):
        if provider == "qq":
            return "QQ 邮箱认证失败。请确认已开启 IMAP 服务，并填写授权码而不是 QQ 密码。"
        if provider in {"163", "126"}:
            return "网易邮箱认证失败。请确认已开启 IMAP 服务并使用客户端授权码；首次使用可能需要在网页端完成短信验证。"
        if provider == "gmail":
            return "Gmail 认证失败。请确认已开启两步验证，并使用 Google 应用专用密码。"
        return "邮箱认证失败，请检查账号、密码或授权码，并确认邮箱已开启 IMAP。"
    if "too many" in lowered or "rate" in lowered:
        return "邮箱服务器限制了登录频率，请稍后再试。"
    if isinstance(exc, imaplib.IMAP4.error):
        cleaned = re.sub(r"\s+", " ", raw).strip()[:240]
        return f"邮箱服务器返回错误：{cleaned}" if cleaned else "邮箱服务器返回未知错误。"
    return "无法连接邮箱，请检查网络和 IMAP 设置后重试。"


class MailboxSession:
    def __init__(self, account: MailAccount, timeout: int = 30) -> None:
        self.account = account
        self.timeout = timeout
        self.conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "MailboxSession":
        account = self.account
        try:
            context = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(account.host, account.port, ssl_context=context, timeout=self.timeout)
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, account.provider)) from exc
        try:
            conn.login(account.username, account.password)
        except Exception as exc:
            try:
                conn.logout()
            except Exception:
                pass
            raise MailboxError(_humanize_error(exc, account.provider)) from exc
        if account.provider in {"163", "126"}:
            self._identify(conn)
        self.conn = conn
        try:
            typ, _ = conn.select(_quote(account.folder or "INBOX"), readonly=True)
            if typ != "OK":
                raise MailboxError("找不到指定的邮件文件夹，请检查文件夹名称（默认是 INBOX）。")
        except MailboxError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise MailboxError(_humanize_error(exc, account.provider)) from exc
        return self

    def _identify(self, conn: imaplib.IMAP4_SSL) -> None:
        try:
            payload = '("name" "campus-video" "version" "1.0" "vendor" "local")'
            typ, data = conn._simple_command("ID", payload)
            conn._untagged_response(typ, data, "ID")
        except Exception:
            pass

    def uidvalidity(self) -> str | None:
        if not self.conn:
            return None
        try:
            typ, data = self.conn.response("UIDVALIDITY")
            if typ == "UIDVALIDITY" and data:
                value = data[0]
                return value.decode("ascii", "ignore") if isinstance(value, bytes) else str(value)
        except Exception:
            pass
        return None

    def search(self, *, since: datetime, last_uid: int = 0, known_uidvalidity: str | None = None, limit: int = 300) -> SearchResult:
        if not self.conn:
            raise MailboxError("邮箱连接尚未建立。")
        uidvalidity = self.uidvalidity()
        incremental = bool(last_uid > 0 and uidvalidity and known_uidvalidity and uidvalidity == str(known_uidvalidity))
        try:
            if incremental:
                typ, data = self.conn.uid("search", None, f"UID {last_uid + 1}:*")
            else:
                typ, data = self.conn.uid("search", None, f'SINCE "{imap_date(since)}"')
            if typ != "OK":
                raise MailboxError("邮箱服务器拒绝了邮件搜索请求。")
            uids = _parse_uid_search_response(data)
            if incremental:
                uids = [uid for uid in uids if uid > last_uid]
            top_uid = max(uids, default=last_uid)
            if limit > 0 and len(uids) > limit:
                uids = uids[-limit:]
                top_uid = max(uids)
            return SearchResult(uids=uids, uidvalidity=uidvalidity, top_uid=top_uid)
        except MailboxError:
            raise
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, self.account.provider)) from exc

    def fetch_raw(self, uid: int) -> bytes:
        if not self.conn:
            raise MailboxError("邮箱连接尚未建立。")
        try:
            typ, data = self.conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if typ != "OK" or not data:
                raise MailboxError("读取邮件内容失败，邮件可能已被移动或删除。")
            for item in data:
                if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
                    return bytes(item[1])
            raise MailboxError("邮箱服务器没有返回可读取的邮件内容。")
        except MailboxError:
            raise
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, self.account.provider)) from exc

    def close(self) -> None:
        conn = self.conn
        self.conn = None
        if not conn:
            return
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def _decode_bytes(payload: bytes, declared: str | None = None) -> str:
    encodings: list[str] = []
    normalized = (declared or "").lower().strip()
    if normalized and normalized not in {"unknown-8bit", "x-unknown", "us-ascii", "ascii", "iso-8859-1", "latin-1"}:
        encodings.append(normalized)
    if normalized in {"us-ascii", "ascii", "iso-8859-1", "latin-1"}:
        encodings.append("utf-8")
    encodings.extend(["utf-8", "gb18030"])
    if normalized:
        encodings.append(normalized)
    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", errors="replace")


def _decode_header(value: Any) -> str:
    if value is None:
        return ""
    try:
        chunks = decode_header(str(value))
    except Exception:
        return str(value)
    output: list[str] = []
    for chunk, charset in chunks:
        if isinstance(chunk, bytes):
            output.append(_decode_bytes(chunk, charset))
        else:
            output.append(chunk)
    return "".join(output).strip()


class _HTMLContentExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "head", "title", "noscript", "svg"}
    BLOCK_TAGS = {"p", "div", "section", "article", "header", "footer", "tr", "li", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
    CELL_TAGS = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[EmailLink] = []
        self._skip_depth = 0
        self._anchors: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value.strip()
                    break
            self._anchors.append({"href": href, "text": []})
        if tag == "br":
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in self.CELL_TAGS:
            self.parts.append("\t")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br" and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._anchors:
            anchor = self._anchors.pop()
            self._register_link(anchor.get("href", ""), "".join(anchor.get("text", [])))
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in self.CELL_TAGS:
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.parts.append(data)
        if self._anchors:
            self._anchors[-1]["text"].append(data)

    def _register_link(self, href: str, text: str) -> None:
        href = href.strip()
        if not href:
            return
        clean_text = re.sub(r"\s+", " ", text).strip()
        self.links.append(EmailLink(url=href, text=clean_text))

    def result(self) -> tuple[str, list[EmailLink]]:
        text = "".join(self.parts)
        return text, self.links


def _clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("\u200b", "")
    lines = []
    for line in value.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text_and_links(html: str) -> tuple[str, list[EmailLink]]:
    parser = _HTMLContentExtractor()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    text, links = parser.result()
    return _clean_text(text), links


def _clean_url(url: str) -> str:
    url = url.strip()
    while url and url[-1] in TRAILING_URL_CHARS:
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    return url


def extract_plain_links(text: str) -> list[EmailLink]:
    links: list[EmailLink] = []
    for match in URL_RE.finditer(text or ""):
        url = _clean_url(match.group(0))
        if url:
            links.append(EmailLink(url=url))
    return links


def parse_raw_email(raw: bytes, fallback_received_at: datetime | None = None) -> ParsedEmail:
    message = BytesParser(policy=default_policy).parsebytes(raw)
    subject = _decode_header(message.get("Subject")).replace("\r", " ").replace("\n", " ").strip()[:500]
    if not subject:
        subject = "（无主题）"
    raw_from = _decode_header(message.get("From"))
    sender_name, sender_email = parseaddr(raw_from)
    sender_name = re.sub(r"\s+", " ", sender_name).strip()[:160]
    sender_email = sender_email.strip()[:254]

    received_at = fallback_received_at or datetime.now(timezone.utc)
    if message.get("Date"):
        try:
            parsed_date = parsedate_to_datetime(str(message.get("Date")))
            if parsed_date is not None:
                received_at = parsed_date if parsed_date.tzinfo else parsed_date.replace(tzinfo=LOCAL_TZ)
        except (TypeError, ValueError, OverflowError):
            pass
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    received_at = received_at.astimezone(timezone.utc)

    plain_parts: list[str] = []
    html_parts: list[str] = []
    links: list[EmailLink] = []

    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type().lower()
        if content_type not in {"text/plain", "text/html"}:
            continue
        if (part.get_content_disposition() or "").lower() == "attachment":
            continue
        if part.get_filename():
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)):
            continue
        text = _decode_bytes(bytes(payload), part.get_content_charset())
        if content_type == "text/html":
            html_text, html_links = html_to_text_and_links(text)
            if html_text:
                html_parts.append(html_text)
            links.extend(html_links)
        else:
            cleaned = _clean_text(text)
            if cleaned:
                plain_parts.append(cleaned)
                links.extend(extract_plain_links(cleaned))

    plain_text = _clean_text("\n\n".join(plain_parts))
    html_text = _clean_text("\n\n".join(html_parts))
    if plain_text and len(plain_text) >= 60:
        body_text = plain_text
    elif html_text:
        body_text = html_text
    else:
        body_text = plain_text

    deduped: dict[str, EmailLink] = {}
    for link in links:
        url = _clean_url(link.url)
        if not url.lower().startswith(("http://", "https://")):
            continue
        existing = deduped.get(url)
        if existing is None or (not existing.text and link.text):
            deduped[url] = EmailLink(url=url, text=link.text.strip()[:300])
    body_text = body_text[:100_000]
    html_text = html_text[:100_000]

    return ParsedEmail(
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        received_at=received_at,
        body_text=body_text,
        html_text=html_text,
        links=list(deduped.values()),
        message_id=str(message.get("Message-ID", "")).strip()[:998],
        list_unsubscribe=_decode_header(message.get("List-Unsubscribe")).strip()[:500],
        precedence=_decode_header(message.get("Precedence")).strip()[:100],
        reply_to=_decode_header(message.get("Reply-To")).strip()[:300],
    )
