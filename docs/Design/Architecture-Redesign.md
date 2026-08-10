# 视频文案分析平台 — 架构重设计方案

> **版本**: v1.0
> **日期**: 2026-08-10
> **状态**: 待执行
> **决策依据**: 用户确认 Q1-B / Q2-A / Q3-A + 目录整理

---

## 1. 设计目标

| 维度 | 当前问题 | 目标状态 |
|------|---------|---------|
| 可维护性 | 1490 行 `server.py` + 1708 行 `analyzer.html`，改一处影响全局 | 按职责拆分为 15+ 个小文件，每个 50-200 行 |
| 运行稳定性 | 转写阻塞 HTTP 线程，网页卡死 | 转写以独立子进程运行，server 始终响应 |
| 可扩展性 | 加新功能不知道放哪 | 服务层/处理器层/组件层有明确归属 |
| 文件组织 | 根目录散落 10+ 个 .py 文件，Model/ 与 Model-s/ 命名混乱 | 4 大目录：`server/` `web/` `scripts/` `data/` |

---

## 2. 新目录结构

```
video-analysis-toolkit/
│
├── server/                          # 后端 Python 代码
│   ├── server.py                    # 入口：HTTP 服务器启动 + 路由注册
│   ├── config.py                    # 路径、常量、.env 加载
│   ├── repository.py                # 数据访问层：library.json / tags.json CRUD
│   │
│   ├── services/                    # 业务逻辑层（无 HTTP 依赖）
│   │   ├── downloader.py           # 视频下载（调用 scripts/vdl.py 为子进程）
│   │   ├── transcriber.py          # 语音转写（调用 scripts/transcribe.py 为子进程）
│   │   ├── analyzer.py             # DeepSeek AI 分析 + 爆款评分
│   │   ├── methodology.py          # 方法论聚合
│   │   └── stats.py               # 统计计算
│   │
│   └── handlers/                    # HTTP 路由处理器（薄层，只做参数解析+响应）
│       ├── library.py              # GET /api/library, POST /api/save, POST /api/delete
│       ├── pipeline.py             # POST /api/process, POST /api/download, POST /api/transcribe, GET /api/progress
│       ├── analyze.py              # POST /api/analyze, POST /api/batch-analyze
│       ├── tags.py                 # GET /api/tags, POST /api/tags (rename/delete/merge)
│       ├── import_video.py         # GET /api/scan-videos, POST /api/import
│       └── files.py               # 静态文件服务：/api/video-file/*, /api/video/*, /sounds/*
│
├── web/                             # 前端 SPA
│   ├── index.html                   # 入口（极简 shell, ~60行）
│   ├── css/
│   │   ├── design-tokens.css       # CSS 变量、字体
│   │   ├── base.css               # reset、布局、滚动条
│   │   ├── components.css          # 按钮、卡片、标签、弹窗、进度条
│   │   └── views.css              # 各视图特有样式
│   ├── js/
│   │   ├── app.js                  # 主入口：初始化 + 路由切换
│   │   ├── api.js                  # fetch 封装（统一错误处理）
│   │   ├── store.js                # 全局状态管理（发布订阅）
│   │   ├── views/
│   │   │   ├── library.js          # 视频库视图
│   │   │   ├── methodology.js      # 方法论视图
│   │   │   └── stats.js            # 统计视图
│   │   ├── components/
│   │   │   ├── video-card.js       # 视频卡片渲染
│   │   │   ├── video-detail.js     # 详情弹窗
│   │   │   ├── add-modal.js        # 添加视频弹窗
│   │   │   ├── pipeline.js         # 管道进度组件
│   │   │   ├── tag-manager.js      # 标签管理弹窗
│   │   │   ├── confirm-modal.js    # 确认弹窗
│   │   │   └── toast.js            # Toast 通知
│   │   └── utils.js                # 工具函数
│   └── assets/
│       └── sounds/
│           └── success.mp3
│
├── scripts/                         # 独立脚本（可单独执行）
│   ├── vdl.py                      # 视频下载
│   ├── transcribe.py               # 语音转写（原 transcribe_videos.py）
│   └── analyze_scripts.py          # 脚本关键词分析
│
├── data/                            # 运行时数据（原 library/）
│   ├── library.json
│   ├── tags.json
│   └── videos/
│       └── {video_id}/
│           ├── video.mp4
│           ├── transcript.json
│           ├── script_analysis.json
│           └── deepseek_report.md
│
├── models/                          # ML 模型文件
│   └── whisper-large-v3-turbo/     # faster-whisper large-v3-turbo（原 Model/）
│
├── third_party/                     # 第三方代码
│   └── TikTokDownloader/           # 原 TikTokDownloader-master/
│
├── docs/                            # 设计文档
│   └── design/
│       └── *.md
│
├── .env                             # 环境变量
├── requirements.txt
├── start.bat                       # 启动脚本：python server/server.py
├── .gitignore
└── README.md
```

### 清理项

| 源路径 | 目标/操作 |
|--------|----------|
| `Model/` | → `models/whisper-large-v3-turbo/` |
| `library/` | → `data/` |
| `TikTokDownloader-master/` | → `third_party/TikTokDownloader/` |
| `sounds/` | → `web/assets/sounds/` |
| `Docs/` | → `docs/` |
| `analyzer.html` | → 拆分为 `web/` 下的多个文件 |
| `server.py` | → 拆分为 `server/` 下的多个文件 |
| `transcribe_videos.py` | → `scripts/transcribe.py` |
| `vdl.py` | → `scripts/vdl.py` |
| `analyze_scripts.py` | → `scripts/analyze_scripts.py` |
| `download_douyin.py` | 废弃/删除（已被 vdl.py 替代） |
| `crawl_user_videos.py` | → `scripts/crawl_user_videos.py` |
| `benchmark.py` | → `scripts/benchmark.py` |
| `real_world_test.py` | → `scripts/real_world_test.py` |
| `web_demo/` | 废弃/删除（已被 web/ 替代） |
| `CLAUDE.md` | 废弃/删除 |
| `.playwright-browsers/` | 保留（自动化依赖） |

---

## 3. 前端架构拆分

### 3.1 技术方案

- **加载方式**: `<script type="module">` 原生 ES Module，零构建工具
- **CSS**: 拆分为 4 个文件，按顺序 `<link>` 引入
- **状态管理**: 发布订阅模式的 Store（替代全局 `S` 对象）
- **依赖**: Chart.js + marked（CDN 引入，保持不变）

### 3.2 模块职责矩阵

| 模块 | 行数(估) | 职责 | 对外暴露 |
|------|---------|------|---------|
| `index.html` | ~60 | HTML shell（app-bar + 三个 view 容器 + 弹窗骨架） | — |
| `css/design-tokens.css` | ~50 | CSS 变量（颜色、圆角、阴影、字体） | — |
| `css/base.css` | ~40 | reset、body、滚动条、排版 | — |
| `css/components.css` | ~400 | 按钮、卡片、标签、弹窗、进度条、stepper、表格 | — |
| `css/views.css` | ~100 | library/stats/methodology 视图特有布局 | — |
| `js/app.js` | ~50 | 初始化、视图路由 `switchView()`、DOM ready | `App` |
| `js/api.js` | ~40 | `fetch` 封装，统一 JSON 解析和错误处理 | `API` |
| `js/store.js` | ~40 | 全局状态 + 事件订阅 `Store.on(event, fn)` | `Store` |
| `js/views/library.js` | ~80 | 视频库渲染、标签筛选、排序、搜索 | `LibraryView` |
| `js/views/methodology.js` | ~50 | 方法论视图加载和渲染 | `MethodologyView` |
| `js/views/stats.js` | ~100 | 统计视图：KPI + Chart.js 图表 | `StatsView` |
| `js/components/video-card.js` | ~80 | 视频卡片 HTML 生成（含 hover 预览、状态图标） | `VideoCard` |
| `js/components/video-detail.js` | ~200 | 详情弹窗：播放器、工作流条、标签页切换、编辑标题/标签 | `VideoDetail` |
| `js/components/add-modal.js` | ~120 | 添加视频弹窗：模式切换、URL 输入、管道触发 | `AddModal` |
| `js/components/pipeline.js` | ~80 | 管道进度：进度条 + 步骤器 + 轮询逻辑 | `Pipeline` |
| `js/components/tag-manager.js` | ~80 | 标签管理弹窗：列表、重命名、删除 | `TagManager` |
| `js/components/confirm-modal.js` | ~30 | 通用确认弹窗 | `ConfirmModal` |
| `js/components/toast.js` | ~30 | Toast 通知 | `toast()` |
| `js/utils.js` | ~20 | `esc()`, `formatTime()`, `debounce()` | 各工具函数 |
| **合计** | **~1650** | — | — |

### 3.3 模块间依赖关系

```
app.js
  ├── store.js          (无依赖)
  ├── api.js            (无依赖)
  ├── views/library.js  ──── 依赖 store.js, api.js, video-card.js
  ├── views/methodology.js ── 依赖 api.js
  ├── views/stats.js    ──── 依赖 api.js, Chart.js
  └── components/
        ├── video-card.js      ──── 依赖 utils.js
        ├── video-detail.js    ──── 依赖 api.js, store.js, confirm-modal.js
        ├── add-modal.js       ──── 依赖 api.js, store.js, pipeline.js
        ├── pipeline.js        ──── 依赖 api.js
        ├── tag-manager.js     ──── 依赖 api.js, confirm-modal.js
        ├── confirm-modal.js   ──── 无依赖
        └── toast.js           ──── 无依赖
```

### 3.4 index.html 骨架（简化示意）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>视频文案分析平台</title>
  <link rel="stylesheet" href="css/design-tokens.css">
  <link rel="stylesheet" href="css/base.css">
  <link rel="stylesheet" href="css/components.css">
  <link rel="stylesheet" href="css/views.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
  <!-- app-bar + views + modals shell -->
  <script type="module" src="js/app.js"></script>
</body>
</html>
```

---

## 4. 后端架构拆分

### 4.1 分层示意

```
┌─────────────────────────────────────────────┐
│  handlers/   (HTTP 层)                       │
│  参数解析 → 调用 service → 格式化响应          │
│  每个文件 50-80 行，纯转发，不含业务逻辑        │
├─────────────────────────────────────────────┤
│  services/   (业务逻辑层)                     │
│  纯 Python 函数，无 HTTP 依赖，可独立测试       │
│  downloader.py / transcriber.py 通过子进程调脚本│
├─────────────────────────────────────────────┤
│  repository.py  (数据访问层)                  │
│  load_library() / save_library() / CRUD      │
├─────────────────────────────────────────────┤
│  config.py  (配置层)                          │
│  BASE_DIR, DATA_DIR, 模型路径, .env 加载      │
└─────────────────────────────────────────────┘
```

### 4.2 模块职责矩阵

| 模块 | 行数(估) | 职责 | 核心函数 |
|------|---------|------|---------|
| `server.py` | ~80 | 启动 ThreadedHTTPServer，注册路由 | `main()` |
| `config.py` | ~30 | 加载 .env，导出路径常量 | `BASE_DIR`, `DATA_DIR`, `MODELS_DIR` |
| `repository.py` | ~60 | library.json / tags.json 读写 | `load_library()`, `save_library()`, `load_tags()`, `save_tags()` |
| `services/downloader.py` | ~100 | 调用 `scripts/vdl.py` 子进程下载，解析输出，进度回调 | `download_video(url, output_dir, progress_cb)` |
| `services/transcriber.py` | ~100 | 调用 `scripts/transcribe.py` 子进程转写，进度回调 | `transcribe_video(video_path, output_path, progress_cb)` |
| `services/analyzer.py` | ~150 | DeepSeek API 调用 + 爆款评分 | `call_deepseek()`, `calculate_viral_score()` |
| `services/methodology.py` | ~80 | 跨视频聚合钩子/模板/案例 | `aggregate_methodology(lib, tag_filter)` |
| `services/stats.py` | ~60 | 统计计算：分布、分组、平均分 | `compute_stats(videos)` |
| `handlers/library.py` | ~40 | /api/library, /api/save, /api/delete | `handle_get_library()`, `handle_save()`, `handle_delete()` |
| `handlers/pipeline.py` | ~80 | /api/process, /api/download, /api/transcribe, /api/progress | `handle_pipeline()`, `handle_transcribe()` |
| `handlers/analyze.py` | ~40 | /api/analyze, /api/batch-analyze | `handle_analyze()`, `handle_batch_analyze()` |
| `handlers/tags.py` | ~50 | /api/tags GET/POST (rename/delete/merge) | `handle_tags()` |
| `handlers/import_video.py` | ~40 | /api/scan-videos, /api/import | `handle_scan()`, `handle_import()` |
| `handlers/files.py` | ~80 | 静态文件：视频 Range 请求、sounds、SPA 首页 | `handle_video_file()`, `handle_sound()`, `handle_index()` |
| **合计** | **~990** | — | — |

### 4.3 server.py 路由注册（简化示意）

```python
# server/server.py
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from server.handlers import library, pipeline, analyze, tags, import_video, files

class APIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if   path == "/":              files.handle_index(self)
        elif path == "/api/library":    library.handle_get(self)
        elif path == "/api/stats":      library.handle_stats(self)
        elif path == "/api/methodology":library.handle_methodology(self)
        elif path == "/api/tags":       tags.handle_get(self)
        elif path == "/api/progress":   pipeline.handle_progress(self)
        elif path.startswith("/api/video-file/"): files.handle_video_file(self)
        elif path.startswith("/api/video/"):      files.handle_video_resource(self)
        elif path.startswith("/sounds/"):         files.handle_sound(self)
        elif path == "/api/scan-videos":          import_video.handle_scan(self)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._parse_json_body()
        if   path == "/api/process":       pipeline.handle_process(self, body)
        elif path == "/api/download":      pipeline.handle_download(self, body)
        elif path == "/api/transcribe":    pipeline.handle_transcribe(self, body)
        elif path == "/api/analyze":       analyze.handle_analyze(self, body)
        elif path == "/api/batch-analyze": analyze.handle_batch(self, body)
        elif path == "/api/save":          library.handle_save(self, body)
        elif path == "/api/delete":        library.handle_delete(self, body)
        elif path == "/api/tags":          tags.handle_post(self, body)
        elif path == "/api/import":        import_video.handle_import(self, body)
```

### 4.4 子进程转写方案（Q2-A）

```
server/services/transcriber.py
  │
  │  subprocess.Popen([sys.executable, "scripts/transcribe.py",
  │      "--input", video_path,
  │      "--output", output_path,
  │      "--model", "models/whisper-large-v3-turbo/"])
  │
  └─→ scripts/transcribe.py
        ├── 加载 WhisperModel (faster-whisper)
        ├── 转写，输出进度到 stdout (JSON 行格式)
        ├── 保存 transcript.json
        └── 退出（释放 GPU 显存）
```

**进度通信协议**：子进程向 stdout 逐行输出 JSON：
```json
{"type":"progress","percent":45,"step":"transcribing"}
{"type":"progress","percent":90,"step":"transcribing"}
{"type":"done","segments":68,"char_count":1820}
```

父进程 `transcriber.py` 通过 `subprocess.PIPE` 逐行读取，回调给前端轮询。

---

## 5. 数据流

### 5.1 全自动管道 (mode=full)

```
用户输入 URL
  │
  ▼
handler/pipeline.py     参数解析，生成 video_id
  │
  ├─→ services/downloader.py    子进程 scripts/vdl.py → data/videos/{id}/video.mp4
  │   └─ 进度：progress_store[video_id] ← stdout 解析
  │
  ├─→ services/transcriber.py   子进程 scripts/transcribe.py → data/videos/{id}/transcript.json
  │   └─ 进度：progress_store[video_id] ← stdout JSON 解析
  │
  ├─→ scripts/analyze_scripts.py (本地关键词分析) → data/videos/{id}/script_analysis.json
  │
  └─→ services/analyzer.py      DeepSeek API → data/videos/{id}/deepseek_report.md
      └─ 写入 library.json: tags, viral_score, status
```

### 5.2 前端轮询进度

```
前端 Pipeline 组件
  │  setInterval 800ms
  ▼
GET /api/progress?video_id=xxx
  │
  ▼
server 全局 progress_store 字典
  │  {"percent": 45, "status": "downloading", "step": "download"}
  ▼
前端更新进度条 + 步骤器状态
```

---

## 6. 迁移计划

### Phase 1: 目录重组（纯文件移动，不改代码）

1. 创建新目录结构：`server/` `web/` `scripts/` `data/` `models/` `third_party/`
2. 移动文件：
   - `Model/` → `models/whisper-large-v3-turbo/`
   - `Model-s/` → `models/whisper-small/`
   - `library/` → `data/`
   - `sounds/` → `web/assets/sounds/`
   - `TikTokDownloader-master/` → `third_party/TikTokDownloader/`
   - `Docs/` → `docs/`
   - `vdl.py` → `scripts/vdl.py`
   - `transcribe_videos.py` → `scripts/transcribe.py`
   - `analyze_scripts.py` → `scripts/analyze_scripts.py`
   - `crawl_user_videos.py` → `scripts/crawl_user_videos.py`
   - `benchmark.py` → `scripts/benchmark.py`
   - `real_world_test.py` → `scripts/real_world_test.py`
3. 更新 `config.py` 中的路径常量
4. 删除废弃：`web_demo/` `CLAUDE.md` `download_douyin.py`

### Phase 2: 后端拆分（server.py → server/ 多文件）

1. 提取 `config.py`（路径、常量、.env 加载）
2. 提取 `repository.py`（library.json / tags.json 的读写函数）
3. 提取 `services/downloader.py`（download_video 函数）
4. 提取 `services/transcriber.py`（transcribe_video_file 函数）
5. 提取 `services/analyzer.py`（call_deepseek + _calculate_viral_score）
6. 提取 `services/methodology.py`（aggregate_methodology）
7. 提取 `services/stats.py`（统计计算）
8. 拆分 handlers/ 6 个文件
9. 精简 `server.py` 为路由注册 + 启动代码
10. 改造 `scripts/transcribe.py` 支持子进程模式（stdout JSON 进度协议）

### Phase 3: 前端拆分（analyzer.html → web/ 多文件）

1. 提取 CSS 到 4 个文件
2. 提取 JS 按模块拆分，建立依赖关系
3. 编写 `index.html` shell
4. 替换 `<script>` 为 `<script type="module">`
5. 验证所有功能正常运行

### Phase 4: 验证与清理

1. 全功能回归测试（下载→转写→分析→浏览→统计）
2. 更新 `start.bat`
3. 更新 `README.md`
4. 删除旧文件 `analyzer.html`（原版）、`server.py`（原版）

---

## 7. 不变项

以下保持不变，确保迁移风险最小：

| 项目 | 不变原因 |
|------|---------|
| JSON 文件存储（Q3-A） | 零依赖，文本可编辑，单用户场景足够 |
| Python `http.server` 基础 | 不引入 FastAPI/Flask，保持最小依赖 |
| Chart.js + marked CDN | 前端依赖最小化 |
| 深色毛玻璃 UI 风格 | 用户偏好的视觉风格 |
| API 端点路径 | 前端代码只需改 import 路径，API 调用不变 |
| progress_store 内存字典 | 单用户场景，无需持久化进度 |

---

## 8. 验收标准

- [ ] `python server/server.py` 一行命令启动
- [ ] 每个后端模块可脱离 HTTP 独立调用（如 `python -c "from server.services.analyzer import call_deepseek; ..."` ）
- [ ] 前端 JS 模块通过 `type="module"` 正常加载，控制台无 404 错误
- [ ] 转写执行时，前端仍可正常浏览视频库、查看其他详情（不被阻塞）
- [ ] 所有现有功能正常：下载/转写/分析/搜索/标签/统计/方法论/批量
- [ ] 根目录文件数从原来的 15+ 个减少到 6 个（`.env` `requirements.txt` `start.bat` `.gitignore` `README.md` + 无后缀杂项）

---

> **下一手**: 请 @system-architect-guardian 审查此架构方案，确认后按 Phase 1-4 顺序开始执行迁移。
