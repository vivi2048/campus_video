---
name: campus-video
version: 1.0.0
description: "从招聘邮箱生成秋招复盘片尾字幕视频：用户提供邮箱、授权码和时间范围，抓取邮件、解析公司流程与结果、生成可精简的文案，并渲染 1:1 黑底滚动字幕 MP4。Use when the user asks for 秋招总结/复盘视频/邮件流程整理/公司结果清单/片尾字幕."
metadata:
  requires:
    bins: ["ffmpeg"]
    python: ["pillow", "pypinyin"]
---

# Campus Video

把“招聘邮箱 → 公司结果清单 → 秋招复盘片尾字幕视频”整理成四步流水线。每一步都有独立命令，可以单独重跑。

## 何时使用

用户提出类似需求时使用：

- “帮我整理秋招邮件，生成公司结果清单”
- “做一个秋招结束视频，像电影片尾字幕一样”
- “把 5 月到现在的招聘邮件做成复盘视频”
- “我有一堆公司结果，想生成黑底滚动字幕”

## 需要向用户收集

1. 邮箱地址
2. 授权码 / 应用专用密码（不是网页登录密码）
3. 邮箱类型：`qq` / `163` / `126` / `gmail` / `custom`
4. 时间范围：`--since YYYY-MM-DD --until YYYY-MM-DD`
5. 输出目录：建议 `work/`
6. 片名：默认 `2027 届秋招复盘`
7. 是否精简名单：`--max-companies N`，0 为全部
8. 是否使用大模型：推荐 `--llm`；若装有 campus-radar，可加 `--from-campus-radar` 复用配置

**安全要求**

- 授权码只通过 `--auth-code`、环境变量 `CAMPUS_MAIL_AUTH_CODE` 或交互式 `getpass` 传入；不要写入文件、不要回显。
- IMAP 只读，不标记已读、不删除、不发送邮件。
- `--llm` 会把邮件正文发送到用户配置的 OpenAI 兼容接口；使用前必须征得用户同意。
- 原始邮件会保存在 `work/emails.jsonl`，提醒用户注意隐私。

## 环境检查

```bash
python campus_video.py doctor
```

需要：Python 3.10+、Pillow、pypinyin、ffmpeg、中文字体。IMAP/MIME 解析已内置在 `mail_utils.py`，**不需要安装 campus-radar**。

如果缺依赖：

```bash
python -m pip install --target .pylibs pillow pypinyin
```

脚本会自动把 `.pylibs` 加入 `sys.path`。

## 四步流程

### 1. 抓邮件

```bash
python campus_video.py fetch \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12
```

授权码可通过 `CAMPUS_MAIL_AUTH_CODE` 环境变量传入，或运行时交互输入。输出 `work/emails.jsonl`。

### 2. 解析公司与流程

推荐使用大模型。若本机装有 campus-radar，可直接复用其中已保存的接口配置（可选）：

```bash
python campus_video.py extract \
  --work work \
  --llm \
  --from-campus-radar
```

`--from-campus-radar` 只是可选的便利项；没有 campus-radar 时，显式传接口配置即可：

```bash
python campus_video.py extract \
  --work work \
  --llm \
  --llm-base-url https://api.deepseek.com/v1 \
  --llm-model deepseek-chat \
  --llm-api-key "$CAMPUS_LLM_API_KEY"
```

不用 LLM 时可直接运行 `extract`，但公司名/阶段会明显粗糙，只适合兜底。

输出 `work/results.jsonl`。

### 3. 生成文案

```bash
python campus_video.py copy \
  --work work \
  --title "2027 届秋招复盘" \
  --max-companies 63
```

输出：

- `work/outcomes.txt`：`公司 结果` 平铺清单
- `work/copy.txt`：片尾文案，可直接手动编辑

如果用户对结果有更正，用 `--overrides`：

```bash
python campus_video.py copy \
  --work work \
  --title "2027 届秋招复盘" \
  --max-companies 63 \
  --overrides overrides.json
```

`overrides.json` 示例：

```json
{
  "公司A": "已 OC",
  "公司B": "二面挂",
  "公司C": "笔试挂"
}
```

如果需要只保留/排除某些公司：

```bash
--keep "公司A,公司B" --drop "公司C"
```

如果用户想自己精简，直接让用户编辑 `work/copy.txt`，然后跳到第 4 步。

### 4. 渲染视频

```bash
python campus_video.py render \
  --copy work/copy.txt \
  --out work/终章_1080x1080.mp4 \
  --duration 30
```

默认规格：

- 1080 × 1080
- 60fps
- 30 秒
- 黑底 + 极轻暗角
- 全篇 36，统一字体、字重、字距、行高
- 三级亮度：片名 / 正文 / 状态
- 开头/结尾 0.8 秒淡入淡出
- 全角标点 + 「」引号

可选：

```bash
--font "C:/Windows/Fonts/NotoSansSC-VF.ttf"
--audio bgm.mp3
--width 1080 --height 1080
--fps 60
--duration 30
```

## 一条命令跑完

```bash
python campus_video.py all \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12 \
  --llm --from-campus-radar \
  --title "2027 届秋招复盘" \
  --max-companies 63 \
  --duration 30
```

## 文案格式

默认文案结构：

```text
{title}

谨以此片
献给每一个在深夜刷新过邮箱的人

领衔主演：本人
主演：面试官
笔试指导：北森、牛客、赛码
面试指导：牛客、小红书

参演名单

公司A 简历挂
公司B 简历挂

公司C 笔试挂
公司D 笔试挂

公司E 一面挂

公司F 已 OC

特别鸣谢

所有发过「感谢您投递」的公司
所有在深夜失效的测评链接
所有「请于 48 小时内完成」的 AI 面试
所有「您的简历已进入人才库」的邮件

以及，终于走到这里的你
```

结果分档固定为：`简历挂 → 笔试挂 → 一面挂 → 二面挂 → 三面挂 → 已 OC`，每档内按拼音 A-Z。

要改文案，直接编辑 `work/copy.txt`；`render` 只依赖这个文件。

## 常见问题

- **QQ 认证失败**：确认开启了 IMAP，使用的是授权码而不是 QQ 密码。
- **163/126 认证失败**：确认开启 IMAP，并使用客户端授权码；首次可能需要网页端短信验证。
- **抓取为空**：检查 `--since/--until`，以及邮件是否在 `INBOX`（默认只读 INBOX）。
- **公司名很乱**：使用 `--llm` 重新跑 `extract`；规则模式只适合兜底。
- **轮次不准**：在 `overrides.json` 里手动指定公司结果，或直接编辑 `copy.txt`。
- **视频没有字幕**：确认 ffmpeg 在 PATH 中，且 `doctor` 全部 OK。
