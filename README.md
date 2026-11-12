# Campus Video

从招聘邮箱生成“秋招复盘”片尾字幕视频。

输入：邮箱地址、授权码、时间范围。  
输出：公司结果清单、可编辑文案、1080×1080 黑底滚动字幕 MP4。

## 安装

```bash
git clone https://github.com/vivi2048/campus_video.git
cd campus_video
python -m pip install --target .pylibs -r requirements.txt
python campus_video.py doctor
```

也可以把整个目录放到 `~/.zcode/skills/campus-video`，作为 ZCode skill 使用。

## 依赖

- Python 3.10+
- `pillow`
- `pypinyin`
- `ffmpeg`
- 无需 `campus-radar`：IMAP/MIME 解析已内置于 `mail_utils.py`

脚本会自动加载同目录下的 `.pylibs`。

## 快速开始

```bash
# 1. 检查环境
python campus_video.py doctor

# 2. 抓邮件（授权码可通过 CAMPUS_MAIL_AUTH_CODE 传入）
python campus_video.py fetch \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12

# 3. 解析（推荐 LLM）
# 有 campus-radar 时，复用其已保存的接口配置：
python campus_video.py extract --work work --llm --from-campus-radar

# 没有 campus-radar 时，显式传接口配置：
python campus_video.py extract --work work --llm \
  --llm-base-url https://api.deepseek.com/v1 \
  --llm-model deepseek-chat \
  --llm-api-key "$CAMPUS_LLM_API_KEY"

# 4. 生成文案
python campus_video.py copy --work work --title "2027 届秋招复盘" --max-companies 63

# 5. 渲染
python campus_video.py render --copy work/copy.txt --out work/终章_1080x1080.mp4
```

也可以一条命令：

```bash
python campus_video.py all \
  --work work \
  --email user@qq.com \
  --provider qq \
  --since 2026-05-01 \
  --until 2026-11-12 \
  --llm --from-campus-radar \
  --title "2027 届秋招复盘" \
  --max-companies 63
```

## 工作目录

```text
work/
├── emails.jsonl      # 原始邮件（解析后的正文）
├── results.jsonl     # 每封邮件的公司/阶段/结果
├── outcomes.txt      # 公司 结果 平铺清单
├── copy.txt          # 片尾文案（可直接编辑）
└── 终章_1080x1080.mp4
```

## 文案编辑

`copy.txt` 就是最终视频的文案。你可以：

- 直接删掉不想要的公司行
- 改片名、献词、主创、特别鸣谢、结尾
- 调整公司顺序（视频按文件顺序滚动）
- 保留空行作为停顿

改完重新渲染：

```bash
python campus_video.py render --copy work/copy.txt --out work/终章_1080x1080.mp4
```

## 结果修正

`extract` 自动判断公司结果，但轮次可能不准。用 `overrides.json` 手动指定：

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

`render` 支持：

```bash
--width 1080 --height 1080
--duration 30 --fps 30
--font "C:/Windows/Fonts/NotoSansSC-VF.ttf"
--audio bgm.mp3
```

默认规格：

- 1080 × 1080
- 30fps
- 30 秒
- 黑底 + 极轻暗角
- 片名 64，其余 36
- 全篇统一字重
- 全角标点 + 「」引号
- 开头/结尾 0.8 秒淡入淡出

## 隐私

- IMAP 只读，不标记已读、不删除、不发送。
- 授权码只通过参数、环境变量或交互输入传入，不写入文件。
- `emails.jsonl` 包含邮件正文，注意保存位置。
- `--llm` 会把邮件正文发送到配置的 OpenAI 兼容接口；不用时走本地规则兜底。

## 目录

```text
campus-video-tool/
├── SKILL.md
├── README.md
├── requirements.txt
├── campus_video.py
├── mail_utils.py
├── templates/
│   └── copy.txt
└── examples/
    └── overrides.json
```
