# Video Analysis Toolkit

视频下载 + 博主分析 + AI 转写 + Web Dashboard — 全平台工具集

## Features

- **多平台视频下载**: 抖音(无水印)/YouTube/Bilibili/TikTok/Twitter 等 1900+ 站点
- **博主数据分析**: 批量爬取视频列表、互动指标、内容分类、趋势分析
- **AI 脚本转写**: faster-whisper GPU 加速，中文语音转文字
- **脚本深度分析**: 语速、关键词密度、开场钩子、情绪词统计
- **Web Dashboard**: 交互式仪表盘，视频播放 + 脚本同步高亮 + Chart.js 图表
- **一键部署**: Cloudflare Tunnel 公网访问

## Quick Start

```bash
# 安装依赖
pip install curl_cffi playwright yt-dlp
playwright install chromium

# 下载单个视频 (自动识别平台)
python vdl.py "https://v.douyin.com/xxx/"
python vdl.py "https://www.youtube.com/watch?v=xxx"

# 抖音单视频无水印下载
python download_douyin.py "https://v.douyin.com/xxx/"

# 批量爬取博主所有视频
python crawl_user_videos.py "https://v.douyin.com/userlink/"

# 批量转写
python transcribe_videos.py --input videos/user_all/ --output web_demo/all_transcripts.json

# 启动分析仪表盘
cd web_demo && python app.py
# → http://localhost:8300
```

## Architecture

```
URL → curl_cffi (TLS fingerprint) → iesdouyin.com → video_id
    → aweme.snssdk.com/aweme/v1/play/ → MP4 (720p, no watermark)

User Page → Playwright API intercept → /aweme/post/ → video list
         → curl_cffi enrich each video → engagement metrics

Videos → faster-whisper large-v3 (GPU) → timestamped transcripts
      → script analysis (speech rate, keywords, hooks, emotions)

Web Demo → Python HTTP server → Chart.js dashboard
        → video player with transcript sync highlighting
        → Cloudflare Tunnel → public URL
```

## File Structure

```
├── vdl.py                    # Universal video downloader (auto-detect platform)
├── download_douyin.py        # Douyin single video (no watermark)
├── crawl_user_videos.py      # Batch crawl user videos + download
├── transcribe_videos.py      # Whisper AI speech-to-text
├── analyze_scripts.py        # Script analysis (speech rate, keywords, hooks)
├── web_demo/
│   ├── app.py                # Web dashboard server
│   ├── data.json             # Video metadata
│   ├── all_transcripts.json  # All transcripts
│   ├── script_analysis.json  # Script analysis data
│   └── thumbnails/           # Video thumbnails
├── benchmark.py              # Performance benchmark
├── real_world_test.py        # Multi-site crawling comparison
└── CLAUDE.md                 # Claude Code project context
```

## Key Technical Insights

### Douyin Download (Overseas)
1. **`iesdouyin.com`** share pages don't trigger captcha (unlike `douyin.com`)
2. **`aweme.snssdk.com/aweme/v1/play/`** (not `playwm`) = no watermark
3. **`curl_cffi`** with `impersonate="chrome120"` bypasses TLS fingerprint detection
4. **Overseas IP limits**: API pagination capped at 15 videos (1 page)
5. **Playwright API intercept**: Most reliable way to get video lists

### Framework Comparison

| Task | curl_cffi | Playwright | Crawl4AI |
|------|:---------:|:----------:|:--------:|
| Known API calls | **Best** (fastest) | Good | OK |
| JS-rendered pages | N/A | **Best** | Good |
| General crawling | Fast | Heavy | **Best** (auto-extract) |
| Anti-bot bypass | **Best** (TLS) | Good (real browser) | Good |

### Script Analysis Findings
- **Speech rate sweet spot**: 300-310 chars/min for Chinese tech content
- **Keyword density**: 2.4-3.0% is optimal (too high = academic, too low = shallow)
- **Hook formulas**: Fear/Cognitive Disruption/Data Impact/Counter-intuitive
- **Save/Like ratio > 40%** = high "archive value" content

## Requirements

```
curl_cffi>=0.5
playwright>=1.40
yt-dlp>=2024.1
faster-whisper>=0.10  # optional, for transcription
```

## License

MIT
