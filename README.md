<div align="center">
  <h2>🎬 Campus Video — 秋招复盘片尾字幕</h2>
  <p>从招聘邮箱生成秋招复盘片尾字幕视频的本地工具</p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-indigo" alt="version">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license">
  <img src="https://img.shields.io/badge/python-3.10%2B-teal" alt="python">
  <img src="https://img.shields.io/badge/offline-ready-green" alt="offline">
</p>

读取招聘邮箱，解析公司、岗位、流程阶段与结果，生成可编辑的片尾文案，并渲染成 1080×1080 黑底滚动字幕 MP4。默认完全本地处理；可选接入 OpenAI 兼容大模型，提升非标准邮件的识别率。

---

## 功能

|          |                                        |
|----------|----------------------------------------|
| **邮箱同步** | 只读 IMAP，支持 QQ、163、126、Gmail 和自定义服务器 |
| **流程解析** | 识别公司、岗位、测评、笔试、AI 面、一面、二面、三面、OC、拒信 |
| **结果清单** | 自动生成“公司 结果”清单，按简历挂 → 笔试挂 → 一面挂 → 二面挂 → 三面挂 → 已OC 排序 |
| **文案生成** | 生成电影片尾格式：片名、献词、主创、参演名单、特别鸣谢、结尾 |
| **文案精简** | 支持限制公司数量、保留/排除指定公司，或直接编辑 `copy.txt` |
| **视频渲染** | 1080×1080、30fps、30 秒、黑底、居中滚动、统一字重、极轻暗角 |
| **自定义** | 片名、时长、帧率、字体、画幅、BGM 均可覆盖 |
| **完全独立** | 内置 IMAP/MIME 解析，无需安装 campus-radar |

## 快速开始

### 安装

```bash
git clone https://github.com/vivi2048/campus_video.git
cd campus_video
python -m pip install --target .pylibs -r requirements.txt
python campus_video.py doctor
```

也可以把整个目录放到 `~/.zcode/skills/campus-video`，作为 ZCode skill 使用。

### 使用

```bash
# 1. 抓邮件（授权码可通过 CAMPUS_MAIL_AUTH_CODE 传入）
python campus_video.py fetch \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12

# 2. 解析（推荐 LLM）
python campus_video.py extract --work work --llm \
  --llm-base-url https://api.deepseek.com/v1 \
  --llm-model deepseek-chat \
  --llm-api-key "$CAMPUS_LLM_API_KEY"

# 3. 生成文案
python campus_video.py copy --work work --title "2027 届秋招复盘" --max-companies 63

# 4. 渲染
python campus_video.py render --copy work/copy.txt --out work/终章_1080x1080.mp4
```

一条命令跑完：

```bash
python campus_video.py all \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12 \
  --llm \
  --llm-base-url https://api.deepseek.com/v1 \
  --llm-model deepseek-chat \
  --llm-api-key "$CAMPUS_LLM_API_KEY" \
  --title "2027 届秋招复盘" \
  --max-companies 63
```

## 文案格式

```text
2027 届秋招复盘

谨以此片
献给每一个在深夜刷新过邮箱的人

领衔主演：本人
主演：面试官
笔试指导：北森、牛客、赛码
面试指导：牛客、小红书

参演名单

公司A 简历挂
公司B 笔试挂
公司C 一面挂
公司D 已OC

特别鸣谢
所有发过「感谢您投递」的公司
所有在深夜失效的测评链接
所有「请于 48 小时内完成」的 AI 面试
所有「您的简历已进入人才库」的邮件

以及，终于走到这里的你
```

`work/copy.txt` 就是最终视频文案，可以直接手动增删、改片名、改结尾，然后重新渲染。

## 结果修正

自动判断的轮次可能不准，用 `overrides.json` 手动指定：

```json
{
  "公司A": "已OC",
  "公司B": "二面挂",
  "公司C": "笔试挂"
}
```

```bash
python campus_video.py copy --work work --overrides overrides.json --max-companies 63
```

合法结果：`简历挂`、`笔试挂`、`一面挂`、`二面挂`、`三面挂`、`已OC`。

## 视频参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--width` / `--height` | `1080` | 画幅 |
| `--duration` | `30` | 时长（秒） |
| `--fps` | `30` | 帧率 |
| `--font` | 自动查找 | 中文字体路径 |
| `--audio` | 无 | BGM 文件，自动混流 |

默认视觉：黑底、极轻中心暗角、片名 64、其余 36、全篇统一字重、开头/结尾 0.8 秒淡入淡出。

## 项目结构

```text
campus_video/
├── SKILL.md              # ZCode skill 说明
├── campus_video.py       # CLI：fetch / extract / copy / render / all
├── mail_utils.py         # 内置只读 IMAP + MIME 解析
├── templates/copy.txt    # 文案模板
├── examples/overrides.json
└── requirements.txt
```

## 隐私

- IMAP 只读，不标记已读、不删除、不发送邮件。
- 授权码只通过参数、环境变量或交互输入传入，不写入文件。
- `work/emails.jsonl` 包含邮件正文，注意保存位置。
- 使用 `--llm` 时，邮件正文会发送到配置的 OpenAI 兼容接口；不用时走本地规则兜底。
- 默认完全本地处理，不上传任何数据。

## 已知限制

- 只读取 `INBOX`，已归档/删除/其他文件夹的邮件不在内。
- 邮件附件、图片、网页内容不解析。
- 规则解析只适合兜底；公司名、轮次建议用 `--llm` 或手动修正。
- “一面/二面”等轮次不一定等于公司内部叫法。
- 定时同步未实现，需要手动运行命令。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

[MIT License](LICENSE)

---

<sub>本项目仅供学习交流，与任何招聘机构无关。请自行核对邮件与结果。</sub>
