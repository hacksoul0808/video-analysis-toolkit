# 产品需求文档：短视频播放量排行榜 (Hot Ranking)

> **版本**: v2.0（适配新架构）
> **日期**: 2026-08-10
> **状态**: 用户已确认，待开发
> **关联文档**:
> - [PRD-VideoAnalyzer.md](file:///g:/video-analysis-toolkit/docs/Design/PRD-VideoAnalyzer.md)
> - [Architecture-Redesign.md](file:///g:/video-analysis-toolkit/docs/Design/Architecture-Redesign.md)

---

## 1. 产品概述

### 1.1 一句话描述

在视频分析平台中新增「排行榜」页签（置于视频库之前），展示抖音 + TikTok 双平台 60s 以内热门视频排行，支持选中查看详情 + 全选批量下载。

### 1.2 核心价值

- **发现爆款素材**：不再盲搜，直接看平台热门视频排行榜，快速定位爆款
- **跨平台对比**：抖音 vs TikTok 双列对比，了解国内外热点差异
- **闭环转化**：看中即下载 → 自动入视频库 → 后续分析一气呵成
- **缓存策略**：排行榜数据本地缓存，避免重复 API 请求

### 1.3 用户故事

> 作为一个内容创作者，我每天打开这个工具，第一眼就能看到抖音和 TikTok 上现在什么视频最火（60s 以内），勾选感兴趣的，点一下按钮就全部下载到我的视频库里，之后再慢慢分析爆款方法论。

### 1.4 MVP 范围（用户已确认）

| 平台 | MVP 状态 | 说明 |
|------|----------|------|
| 抖音 | ✅ 首期实现 | 复用 TikTokDownloader 热榜 API |
| TikTok | ✅ 首期实现 | 需要新增数据采集模块 |
| 快手 | 🔜 预留 Tab | Tab 按钮显示 "即将上线" |
| 小红书 | 🔜 预留 Tab | Tab 按钮显示 "即将上线" |
| YouTube | 🔜 预留 Tab | Tab 按钮显示 "即将上线" |
| B站 | 🔜 预留 Tab | Tab 按钮显示 "即将上线" |

---

## 2. 架构集成（适配新架构）

### 2.1 与现有系统的关系

```
web/ (前端 SPA，ES Module)
├── index.html                           ← 新增大 Tab 按钮
├── js/
│   ├── app.js                           ← switchView() 增加 'ranking' case
│   ├── store.js                         ← 新增 ranking 状态字段
│   ├── views/
│   │   └── ranking.js                   ← [NEW] 排行榜视图控制器
│   └── components/
│       ├── ranking-table.js             ← [NEW] 左列：排行表格组件
│       ├── ranking-detail.js            ← [NEW] 右列：视频详情面板
│       ├── ranking-platform-tabs.js     ← [NEW] 平台子 Tab 组件
│       └── batch-download-bar.js        ← [NEW] 批量下载进度条
│
server/ (后端)
├── server.py                            ← 路由注册：新增 /api/ranking/* 路由
├── handlers/
│   └── ranking.py                       ← [NEW] 排行 HTTP 处理器（薄层）
├── services/
│   └── ranking_service.py               ← [NEW] 排行采集 + 缓存 + 批量下载
├── repository.py                        ← 下载完成后写入 data/library.json
└── config.py                            ← 新增缓存路径常量

third_party/TikTokDownloader/
└── src/interface/
    └── trending_tiktok.py               ← [NEW] TikTok 排行采集模块

data/
└── ranking_cache.json                   ← [NEW] 排行数据缓存文件
```

### 2.2 技术约束

- **前端**：在 `web/` 目录下新增 `ranking.js` 视图 + 4 个组件，通过 ES Module `import` 引入
- **后端**：新增 `handlers/ranking.py`（薄路由层）+ `services/ranking_service.py`（业务逻辑）
- **数据采集**：抖音热榜复用 `third_party/TikTokDownloader/src/interface/hot.py` 逻辑，TikTok 需新建 `trending_tiktok.py`
- **端口**：沿用现有 8840 端口
- **缓存**：`data/ranking_cache.json` JSON 文件缓存，避免频繁请求外部 API
- **下载**：复用 `services/downloader.py` → `scripts/vdl.py` 子进程模式

---

## 3. 数据模型

### 3.1 排行榜缓存文件

`data/ranking_cache.json`：

```json
{
  "douyin": {
    "updated_at": "2026-08-10T12:00:00Z",
    "videos": [
      {
        "id": "7478499889047260476",
        "rank": 1,
        "title": "马斯克叹服！中国AI新突破",
        "author": "科技猩球",
        "play_count": 12800000,
        "duration_sec": 45,
        "cover_url": "https://p3-dy-xxx/cover.jpg",
        "tags": ["AI", "科技"],
        "platform": "douyin",
        "share_url": "https://v.douyin.com/xxx/"
      }
    ]
  },
  "tiktok": {
    "updated_at": "2026-08-10T12:00:00Z",
    "videos": [
      {
        "id": "7481234567890123456",
        "rank": 1,
        "title": "This AI tool will blow your mind",
        "author": "@techreview",
        "play_count": 15600000,
        "duration_sec": 38,
        "cover_url": "https://p16-sign-useast2a.tiktokcdn.com/xxx.jpg",
        "tags": ["AI", "tech"],
        "platform": "tiktok",
        "share_url": "https://www.tiktok.com/@techreview/video/xxx"
      }
    ]
  }
}
```

### 3.2 缓存刷新策略

| 条件 | 行为 |
|------|------|
| 首次访问 | 后端拉取全量排行 + 逐个查询视频详情 → 过滤 ≤60s → 写入缓存 |
| 缓存存在 + 距上次 < 30分钟 | 直接返回缓存数据 |
| 缓存存在 + 距上次 ≥ 30分钟 | 后台异步刷新，前端仍先用旧缓存返回 |
| 手动点击「刷新排行」按钮 | 同步刷新当前平台排行 |

---

## 4. UI 设计

### 4.1 页签位置

```
┌──────────────────────────────────────────────────┐
│  🔬 Video Script Analyzer    [添加视频] [批量链接] │
├──────────────────────────────────────────────────┤
│  ┌─ Tabs (顶部导航) ──────────────────────────┐  │
│  │ [🏆 排行榜] [🎬 视频库] [💡 方法论库] [📊 统计看板] │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  ┌─ 平台子 Tab (ranking-platform-tabs.js) ────┐  │
│  │ [🔥 抖音] [🌍 TikTok] [⏳ 快手] [⏳ 小红书] ...│  │
│  │          ← 选中：激活态高亮                 │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  ┌─ 2 列布局 (ranking.js 视图) ──────────────┐   │
│  │  左列 60%                 │  右列 40%       │  │
│  │  ranking-table.js         │  ranking-detail │  │
│  │                          │  .js             │  │
│  │  ┌─ 工具栏 ──────────┐   │  ┌─ 视频预览 ─┐ │  │
│  │  │[☐全选] [⬇批量下载] │   │  │              │ │  │
│  │  │         [刷新排行]  │   │  │  <video>    │ │  │
│  │  └───────────────────┘   │  │  自动播放    │ │  │
│  │                          │  │  (静音)      │ │  │
│  │  ┌─ 排行表格 ────────┐   │  │              │ │  │
│  │  │ #  标题    播放量  │   │  └──────────────┘ │  │
│  │  │ ─ ─ ─ ─ ─ ─ ─ ─ ─│   │                   │  │
│  │  │☐ 1 视频A   1280万 │   │  标题: ...        │  │
│  │  │☐ 2 视频B    960万 │   │  作者: ...        │  │
│  │  │☐ 3 视频C    820万 │   │  时长: 45s        │  │
│  │  │  ...              │   │  播放: 1280万     │  │
│  │  │                   │   │  标签: #AI #科技   │  │
│  │  └───────────────── ─┘   │                   │  │
│  │                          │  [查看详情]       │  │
│  │  [◀ 上一页] 第1/10页    │  [下载并分析]     │  │
│  │  [下一页 ▶]             │                   │  │
│  └──────────────────────────┴───────────────────┘  │
│  ┌─ 批量下载进度条 (batch-download-bar.js) ────┐   │
│  │  [下载中: 5/12] ████████░░░░░░░░░░░░ 42%    │   │
│  └─────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

### 4.2 前端组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| 排行榜视图 | `web/js/views/ranking.js` | 初始化子组件、协调 API 调用、处理视图切换时的销毁/重建 |
| 平台子 Tab | `web/js/components/ranking-platform-tabs.js` | 渲染 6 个平台 Tab（2 激活 + 4 预留），处理切换事件 |
| 排行表格 | `web/js/components/ranking-table.js` | 渲染表格行、全选联动、翻页、行选中高亮 |
| 详情面板 | `web/js/components/ranking-detail.js` | 渲染右侧视频预览 + 元数据 + 操作按钮，响应选中事件 |
| 批量下载进度条 | `web/js/components/batch-download-bar.js` | 底部进度条，轮询 `/api/ranking/batch-progress`，非阻塞 |

### 4.3 左列 — 排行表格

| 列 | 宽度 | 内容 | 交互 |
|----|------|------|------|
| ☐ 勾选 | 40px | 复选框 | 点击切换选中，顶部「全选」联动 |
| # 排名 | 48px | 1-100 | 普通文本 |
| 🎬 封面 | 64px | 视频封面缩略图 (img) | — |
| 标题 | flex | 视频标题，最多 2 行 | 点击选中该行 → 右侧加载详情 |
| ⏱ 时长 | 56px | "45s" | 灰色小字 |
| ▶️ 播放量 | 100px | "1280万"（超过万用万/亿单位） | 右对齐 |

**选中行高亮**：点击行 → 蓝色边框高亮 → 右侧面板加载该视频详情。

### 4.4 右列 — 视频详情面板

| 区域 | 内容 |
|------|------|
| 视频预览 | `<video>` 标签，静音自动播放 5s 循环 (复用 Card-Video-Cover-Spec 逻辑) |
| 基本信息 | 标题 (可点击跳转原链接)、作者、时长、播放量 |
| 标签 | 标签云展示 |
| 操作按钮 | `[查看详情]` 打开现有视频库详情弹窗（如果已下载）；`[下载并分析]` 触发单视频下载入视频库 |

### 4.5 平台子 Tab 状态

| Tab | MVP 状态 | 展示 |
|-----|----------|------|
| 🔥 抖音 | 已激活 | 显示排行表格 |
| 🌍 TikTok | 已激活 | 显示排行表格 |
| ⏳ 快手 | 预留 | 点击弹出 Toast "即将上线" |
| ⏳ 小红书 | 预留 | 点击弹出 Toast "即将上线" |
| ⏳ YouTube | 预留 | 点击弹出 Toast "即将上线" |
| ⏳ B站 | 预留 | 点击弹出 Toast "即将上线" |

### 4.6 空状态

| 场景 | UI 表现 |
|------|---------|
| 排行数据加载中 | 骨架屏 Shimmer（表格行占位闪烁） |
| 排行数据为空 | 插画 + "暂无排行数据" + `[刷新排行]` 按钮 |
| API 请求失败 | 错误信息 + `[重试]` 按钮 |
| 未选中任何视频 | 右侧面板显示 "点击左侧视频查看详情" 引导文案 |
| 批量下载完成 | Toast "所选视频已全部加入下载队列" |

### 4.7 视觉风格

- 沿用现有**深色毛玻璃**主题（背景 `#0f0f1a`，主色 `#7c9ff5`）— CSS 变量来自 `web/css/design-tokens.css`
- 排行榜特有样式追加到 `web/css/views.css`
- 表格行 hover 半透明高亮
- 排行前三名特殊标识：🥇 #FFD700 / 🥈 #C0C0C0 / 🥉 #CD7F32 排名色
- 选中行蓝色左边框 + 背景微亮
- 分页按钮圆角 8px，玻璃质感

---

## 5. API 端点设计

### 5.1 获取排行数据

```
GET /api/ranking/{platform}?page=1&page_size=50

Handler: server/handlers/ranking.py → handle_get_ranking()
Service:  server/services/ranking_service.py → get_ranking()

参数:
  platform: "douyin" | "tiktok"
  page: 页码 (默认 1)
  page_size: 每页数量 (默认 50，最大 100)

响应:
{
  "platform": "douyin",
  "total": 100,
  "page": 1,
  "page_size": 50,
  "total_pages": 2,
  "videos": [
    {
      "id": "...",
      "rank": 1,
      "title": "...",
      "author": "...",
      "play_count": 12800000,
      "duration_sec": 45,
      "cover_url": "...",
      "tags": ["AI", "科技"],
      "share_url": "..."
    }
  ],
  "cached_at": "2026-08-10T12:00:00Z",
  "is_stale": false
}
```

- `is_stale: true` 表示缓存已过期（> 30分钟），前端可展示「数据可能不是最新」提示
- 首次加载返回全量数据（≤100 条），前端只展示第一页，翻页不做新请求（前端分页）
- 前端调用：`RankingView` 通过 `API.get('/api/ranking/douyin')` 获取

### 5.2 批量下载

```
POST /api/ranking/batch-download

Handler: server/handlers/ranking.py → handle_batch_download()
Service:  server/services/ranking_service.py → batch_download()

Body:
{
  "platform": "douyin",
  "video_ids": ["id1", "id2", "id3"],
  "auto_analyze": false
}

响应:
{
  "status": "queued",
  "queued_count": 3,
  "skipped_count": 1,
  "failed_count": 0,
  "items": [
    {
      "video_id": "id1",
      "status": "queued",
      "share_url": "https://..."
    }
  ]
}
```

- 批量下载入队后，后台顺序调用 `services/downloader.py → scripts/vdl.py` 子进程下载，不阻塞
- 下载完成后通过 `repository.py` 写入 `data/library.json`
- 前端每 2s 轮询下载进度
- **不再调用 AI 分析**（用户 Q4 选择 B：仅下载，手动到视频库分析）

### 5.3 批量下载进度

```
GET /api/ranking/batch-progress?platform=douyin

Handler: server/handlers/ranking.py → handle_batch_progress()

响应:
{
  "total": 12,
  "completed": 5,
  "downloading": 1,
  "failed": 1,
  "current": { "title": "...", "progress": 67 }
}
```

前端 `batch-download-bar.js` 轮询此端点，更新进度条。

### 5.4 刷新排行

```
POST /api/ranking/{platform}/refresh

Handler: server/handlers/ranking.py → handle_refresh_ranking()

响应:
{
  "status": "refreshing",
  "estimated_sec": 30
}
```

前端行为：按钮变灰 + spinner → 轮询 `GET /api/ranking/{platform}` 直到 `is_stale === false` → 刷新当前页。

### 5.5 server.py 路由注册（新增部分）

```python
# server/server.py  do_GET / do_POST 中新增

# GET 路由
elif path.startswith("/api/ranking/") and "/batch-progress" not in path:
    ranking.handle_get_ranking(self)
elif path == "/api/ranking/batch-progress":
    ranking.handle_batch_progress(self)

# POST 路由
elif path == "/api/ranking/batch-download":
    ranking.handle_batch_download(self, body)
elif path.endswith("/refresh"):
    ranking.handle_refresh_ranking(self)
```

---

## 6. 后端数据采集流水线

### 6.1 抖音排行采集（复用 TikTokDownloader）

```
入口: GET /api/ranking/douyin
  → handlers/ranking.py::handle_get_ranking()
    → services/ranking_service.py::get_ranking("douyin")

流程:
1. 检查 data/ranking_cache.json 中 douyin 缓存
2. 如缓存有效 (< 30min) → 直接返回
3. 如缓存过期 → 后台异步触发采集，先返回旧数据 (is_stale: true)
4. 如无缓存 → 同步采集
   a. 调用抖音热榜 API: /aweme/v1/web/hot/search/list/
     （复用 third_party/TikTokDownloader/src/interface/hot.py 逻辑）
   b. 获取热榜 Top 100 视频列表
   c. 逐个请求视频详情: /aweme/v1/web/aweme/detail/
   d. 过滤 duration_sec <= 60
   e. 按 play_count 降序排列
   f. 写入 data/ranking_cache.json
   g. 返回前端
```

### 6.2 TikTok 排行采集（新增）

```
入口: GET /api/ranking/tiktok
  → handlers/ranking.py::handle_get_ranking()
    → services/ranking_service.py::get_ranking("tiktok")

方案选择:
- 方案 A: TikTok 官方 Research API (需申请权限)
- 方案 B: TikTok 非官方 API (需逆向)
- 方案 C: 第三方数据平台 API (如 TikAPI, RapidAPI)
- 方案 D: 复用 TikTokDownloader 已有 TikTok 接口模板

推荐: 方案 D，新建 third_party/TikTokDownloader/src/interface/trending_tiktok.py
```

**TikTok 采集模块骨架** (`third_party/TikTokDownloader/src/interface/trending_tiktok.py`)：

```python
# 继承或参考 template.py 中的 APITikTok 基类
# 实现 get_trending_list() → 返回 Top 100 视频列表
# 实现 get_video_detail(video_id) → 返回播放量/时长/封面等字段
```

### 6.3 缓存策略

```
data/ranking_cache.json 结构:
{
  "douyin": {
    "updated_at": "ISO_TIMESTAMP",
    "videos": [...]
  },
  "tiktok": {
    "updated_at": "ISO_TIMESTAMP",
    "videos": [...]
  }
}

刷新逻辑 (services/ranking_service.py::_check_cache):
- 缓存 < 30分钟 → 直接返回 (is_stale: false)
- 缓存 >= 30分钟 且 < 2小时 → 返回旧数据, 后台刷新 (is_stale: true)
- 缓存 >= 2小时 或 不存在 → 同步刷新后返回 (阻塞)
- 用户手动点击 [刷新排行] → 强制同步刷新, 忽略缓存时间
```

### 6.4 配置常量（追加到 config.py）

```python
# server/config.py 新增
RANKING_CACHE_FILE = DATA_DIR / "ranking_cache.json"
RANKING_CACHE_TTL_SECONDS = 30 * 60     # 30分钟
RANKING_CACHE_MAX_AGE_SECONDS = 2 * 60 * 60  # 2小时
```

---

## 7. 批量下载流程

### 7.1 用户操作流

```
用户打开排行榜
  → 切换到 [🔥 抖音] 子 Tab  (ranking-platform-tabs.js 触发 switchPlatform)
  → 浏览排行列表  (ranking-table.js 渲染)
  → 点击 [☐ 全选] 勾选当前页 50 个视频
  → （或手动勾选特定视频）
  → 点击 [⬇ 批量下载]
  → ranking.js 调用 confirm-modal.js 弹出确认弹窗: "将下载 12 个视频，确定？"
  → 确认 → API.post('/api/ranking/batch-download', { ... })
  → batch-download-bar.js 显示底部进度条
  → 轮询 API.get('/api/ranking/batch-progress?platform=douyin')
  → 逐个下载完成 → toast("12 个视频已加入下载队列，可在视频库查看")
  → 切换到 [🎬 视频库] Tab → 看到新下载的视频
```

### 7.2 后端队列管理

```
services/ranking_service.py 中的下载队列 (模块级变量):

batch_queue = {}   # key: platform, value: { items: [...], total: N, completed: N }

队列限制:
- 单次批量最多 50 个（一页全选）
- 顺序下载（避免被平台限流封 IP）
- 复用 services/downloader.py 的子进程调用模式
- 单个视频下载失败 → 跳过继续下一个，不阻塞队列
- 已在视频库中的视频 → 自动跳过，标记 skipped

进度通信:
services/ranking_service.py 维护 batch_queue 内存字典
→ handlers/ranking.py::handle_batch_progress() 读取并返回 JSON
→ 前端 batch-download-bar.js 每 2s 轮询
```

### 7.3 前端 Store 状态扩展

```javascript
// web/js/store.js 新增字段
Store.state.ranking = {
  platform: 'douyin',          // 当前选中平台
  data: [],                    // 全量排行数据
  currentPage: 1,             // 当前页码
  pageSize: 50,               // 每页条数
  selectedIds: new Set(),     // 已勾选的 video_id
  selectedDetail: null,       // 当前选中的视频详情
  isStale: false,             // 数据是否过期
  batchDownloading: false,    // 是否正在批量下载
  batchProgress: null         // 批量下载进度 { total, completed, ... }
};
```

---

## 8. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `web/index.html` | **修改** | Tab 栏新增「排行榜」按钮（位于视频库之前） |
| `web/css/views.css` | **修改** | 新增排行榜专属样式（排行表格、2列布局、前三名特殊色） |
| `web/js/app.js` | **修改** | `switchView()` 增加 `'ranking'` case，初始化 `RankingView` |
| `web/js/store.js` | **修改** | 新增 `state.ranking` 状态树 |
| `web/js/views/ranking.js` | **新建** | 排行榜视图控制器（~80行） |
| `web/js/components/ranking-table.js` | **新建** | 排行表格组件（~120行） |
| `web/js/components/ranking-detail.js` | **新建** | 右侧详情面板组件（~80行） |
| `web/js/components/ranking-platform-tabs.js` | **新建** | 平台子 Tab 组件（~40行） |
| `web/js/components/batch-download-bar.js` | **新建** | 批量下载进度条组件（~50行） |
| `server/server.py` | **修改** | `do_GET` / `do_POST` 新增 `/api/ranking/*` 路由（~20行） |
| `server/handlers/ranking.py` | **新建** | 排行 HTTP 处理器（薄层，~80行） |
| `server/services/ranking_service.py` | **新建** | 排行采集 + 缓存 + 批量下载逻辑（~200行） |
| `server/config.py` | **修改** | 新增 `RANKING_CACHE_FILE` 等常量（~5行） |
| `third_party/TikTokDownloader/src/interface/trending_tiktok.py` | **新建** | TikTok 排行采集模块（~100行） |
| `data/ranking_cache.json` | **新建** | 运行时自动生成，排行数据缓存 |

**不修改的文件**：
- `scripts/vdl.py`（复用现有下载逻辑）
- `server/services/downloader.py`（复用子进程下载）
- `server/handlers/pipeline.py`（不依赖排行榜）
- `server/repository.py`（下载完成后由 `ranking_service` 直接写入 `data/library.json`，兼容现有格式）

---

## 9. 分页逻辑

### 9.1 加载策略

| 策略 | 说明 |
|------|------|
| **首次加载** | 后端返回全量（≤100 条），前端只渲染第 1 页 |
| **翻页** | 纯前端分页 — 从 Store 中 `ranking.data` 数组切片，不触发新 API 请求 |
| **加载更多** | 若总数 > 100，底部显示「加载更多」按钮（调用 API `?page=2`） |
| **切换平台** | 清空当前数据 → 重新请求对应平台的排行数据 |

### 9.2 页码组件

```
[◀ 上一页] [1] [2] [3] ... [10] [下一页 ▶]
```

- 当前页高亮
- 首尾页始终显示，中间省略号
- 每页固定 50 条

---

## 10. 边缘情况处理

| 场景 | 处理 |
|------|------|
| 抖音 API 请求超时 | 返回缓存数据 + "数据已过期" 提示 + 重试按钮 |
| TikTok API 不可用 | 显示"TikTok 排行暂时不可用" + 重试按钮 |
| 排行中全部视频 > 60s | 显示"当前排行中暂无 60s 以内视频，请稍后再试" |
| 批量下载中关闭页面 | 后台继续下载，下次打开视频库可见已完成的 |
| 选中视频已在视频库中 | 批量下载时自动跳过，弹窗提示"N 个视频已在库中，已跳过" |
| 排行榜刷新期间用户切换 Tab | 后台继续刷新，不中断 |
| 同一视频在不同平台出现 | 不做去重，各自保留 |
| `ranking.js` 视图被销毁 | `cleanup()` 中停止所有轮询定时器 |

---

## 11. 验收标准

### 11.1 排行榜视图

- [ ] 排行榜 Tab 在视频库 Tab 左侧，默认激活
- [ ] 平台子 Tab 正常切换（抖音 / TikTok）
- [ ] 预留平台 Tab 点击弹出 "即将上线" Toast
- [ ] 排行表格正确展示排名、封面、标题、时长、播放量
- [ ] 前三名有金银铜色特殊标识
- [ ] 点击行 → 右侧详情面板更新
- [ ] 右侧视频封面预览正常加载（复用 Card-Video-Cover-Spec 逻辑）
- [ ] 未选中时右侧显示引导文案
- [ ] 翻页按钮正常、页码组件正确
- [ ] 首次加载在 3s 内完成（有缓存）
- [ ] 切换到其他 Tab 后，排行榜轮询被正确清理

### 11.2 批量下载

- [ ] 全选框正常联动当前页所有行
- [ ] 手动勾选/取消勾选正常
- [ ] 点击「批量下载」弹出确认弹窗
- [ ] 确认后显示底部进度条
- [ ] 列表中有已下载视频 → 确认弹窗提示跳过
- [ ] 下载完成后视频出现在视频库
- [ ] 下载失败的视频不阻塞队列

### 11.3 缓存与刷新

- [ ] 首次加载触发后端采集
- [ ] 30 分钟内再次访问使用缓存
- [ ] 超过 30 分钟提示数据可能过期

### 11.4 四态覆盖

- [ ] 加载态：骨架屏
- [ ] 空态：引导文案 + 刷新按钮
- [ ] 异常态：错误信息 + 重试按钮
- [ ] 正常态：排行榜展示

### 11.5 架构合规

- [ ] `handlers/ranking.py` 行数 < 100，仅做参数解析 + 调用 service
- [ ] `services/ranking_service.py` 行数 < 250，所有业务逻辑独立可测试
- [ ] 前端组件各自独立，通过 Store 通信
- [ ] 无跨模块循环依赖

---

## 12. 开发阶段

| 阶段 | 内容 | 涉及文件 |
|------|------|----------|
| **Phase 1** | 后端：`services/ranking_service.py` + `handlers/ranking.py` + 抖音排行采集 | 新建 `ranking_service.py`, `ranking.py`；修改 `server.py`, `config.py` |
| **Phase 2** | 前端：`ranking.js` 视图 + `ranking-table.js` + `ranking-detail.js` + `ranking-platform-tabs.js` | 新建 4 个前端文件；修改 `app.js`, `store.js`, `views.css`, `index.html` |
| **Phase 3** | 后端：批量下载 + 进度轮询 + 预留平台 Tab 端点 | 修改 `ranking_service.py`, `ranking.py` |
| **Phase 4** | 前端：`batch-download-bar.js` + 全选/批量下载交互 | 新建 `batch-download-bar.js`；修改 `ranking.js`, `ranking-table.js` |
| **Phase 5** | 后端：TikTok 排行采集 `trending_tiktok.py` | 新建 `trending_tiktok.py` |
| **Phase 6** | 四态覆盖 + 空状态 + 异常处理 | 修改前端各组件 |

**建议执行顺序**：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

---

## 13. 交接说明

### 13.1 To 架构师 (@system-architect-guardian)

> 需求已更新至新架构。请审查以下要点：
> 1. `services/ranking_service.py` 和 `handlers/ranking.py` 的职责边界是否合理
> 2. 前端 5 个新组件的模块划分和 Store 状态设计是否合理
> 3. TikTok 排行数据采集 `trending_tiktok.py` 的技术方案（确认复用模板还是需要完全独立实现）
> 4. 批量下载队列的并发控制策略（是否需要限制同时下载数）

### 13.2 To 前端开发 (@vibe-maker)

> 需求已适配新架构。核心变更在 `web/` 目录：
> - 在 `index.html` Tab 栏最前面插入「排行榜」按钮
> - 新建 `web/js/views/ranking.js` 作为视图入口
> - 新建 4 个组件文件（表格/详情/Tab/进度条）
> - 在 `store.js` 中扩展 `state.ranking`
> - 在 `views.css` 中追加排行榜专属样式
> - 详情参考本文档第 4 节 UI 设计

### 13.3 To 后端开发

> 需求已适配新架构。核心变更在 `server/` 目录：
> - 新建 `handlers/ranking.py`（薄路由层）
> - 新建 `services/ranking_service.py`（核心业务逻辑）
> - 在 `server.py` 中注册 4 个新路由
> - 在 `config.py` 中追加缓存常量
> - 新建 `third_party/TikTokDownloader/src/interface/trending_tiktok.py`
> - 详情参考本文档第 5-7 节

---

> **文档状态**: ✅ 用户已确认所有决策，已适配新架构，可进入开发阶段
