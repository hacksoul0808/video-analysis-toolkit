# 产品需求文档：视频互动数据采集 (Video Metrics Collection)

> **版本**: v1.0
> **日期**: 2026-08-10
> **状态**: 需求已确认，待开发

---

## 1. 背景与动机

当前视频下载流程仅采集 6 个元数据字段（`video_id`、`title`、`platform`、`url`、`filename`、`file_size_mb`），`library.json` 中所有视频的 `metrics` 字段均为空对象 `{}`。

然而，前端已有"按点赞数排序"按钮（[library.js](file:///g:/video-analysis-toolkit/web/js/views/library.js#L45-L46)）和统计面板展示 `total_likes` / `avg_likes`（[stats.py](file:///g:/video-analysis-toolkit/server/services/stats.py#L17-L25)），因数据始终为 0，这些功能处于休眠状态。

**技术可行性已验证**：抖音 `iesdouyin.com/share/video/` HTML 响应和 `aweme/post` API 响应中均包含完整 `statistics` 对象，当前代码已访问这些 API 但仅提取了标题和 video_id，互动数据被全部丢弃。

## 2. 需求范围

### 2.1 采集字段（Q1 选择：全部都要 ✅）

| 字段 | JSON Key | 含义 | 来源 |
|------|----------|------|------|
| 点赞数 | `digg_count` | 视频获赞总数 | `aweme.statistics` |
| 评论数 | `comment_count` | 评论总数 | `aweme.statistics` |
| 分享数 | `share_count` | 分享总数 | `aweme.statistics` |
| 播放量 | `play_count` | 播放总数 | `aweme.statistics` |
| 收藏数 | `collect_count` | 收藏总数 | `aweme.statistics` |

### 2.2 library.json metrics 结构

```json
{
  "metrics": {
    "likes": 14200,
    "comments": 890,
    "shares": 3200,
    "plays": 156000,
    "collects": 6300
  }
}
```

> **兼容性注意**：当前 `import_video.py` 中 metrics 用 `"likes"` / `"comments"` / `"shares"` / `"collects"` 命名，新采集的 API 原始字段为 `digg_count` / `comment_count` / `share_count` / `collect_count` / `play_count`。入库时需做字段映射：`digg_count → likes`, `comment_count → comments`, `share_count → shares`, `collect_count → collects`, `play_count → plays`。

### 2.3 现有视频补抓（Q2 选择：批量刷新 ✅）

提供"补抓 metrics"批量刷新功能，对 library.json 中所有（或筛选后的）已有视频重新请求互动数据并更新。

## 3. 改动清单

### 3.1 `scripts/vdl.py` — 内置抖音下载器

**文件**：[vdl.py](file:///g:/video-analysis-toolkit/scripts/vdl.py)

**改动位置**：`download_douyin_builtin()` 函数，第 134-152 行。

**现状**：
```python
resp = session.get(share_url, ...)
m = re.search(r'video_id=([a-zA-Z0-9_]+)', resp.text)    # 仅提取 internal_id
m = re.search(r'"desc"\s*:\s*"([^"]*)"', resp.text)      # 仅提取标题
```

**改动**：在提取 `internal_id` 和 `title` 之后，从 `resp.text` 中解析 `statistics` 对象，通过 stdout 输出 `METRICS:` 行供上层解析。

**实现策略**：

抖音 `iesdouyin.com/share/video/{video_id}/` 的 HTML 中内嵌了 JSON 数据（`window._ROUTER_DATA` 或 `window.__INITIAL_STATE__`），其中路径大致为 `loaderData["video_(id)/page/video"]["videoInfoRes"]["item_list"][0]["statistics"]`。

推荐方案：用正则从 HTML 中提取包含 `statistics` 的 JSON 片段：

```python
# 提取 statistics JSON 块
m = re.search(r'"statistics"\s*:\s*\{[^}]+\}', resp.text)
if m:
    try:
        stats = json.loads('{' + m.group(0) + '}')
        stats_obj = stats.get("statistics", {})
        print(f"METRICS:{json.dumps(stats_obj, ensure_ascii=False)}")
    except json.JSONDecodeError:
        pass  # 静默失败，不影响下载主流程
```

**关键原则**：metrics 提取失败不应阻塞视频下载。即使 statistics 解析失败，仍应继续下载流程。

### 3.2 `server/services/downloader.py` — 下载服务

**文件**：[downloader.py](file:///g:/video-analysis-toolkit/server/services/downloader.py)

**改动位置**：`download_video()` 函数，第 87-119 行（解析 stdout 提取元数据部分）。

**现状**：仅从 stdout 解析 `标题:` 和 `PROGRESS:`。

**改动**：新增解析 `METRICS:` 行，将互动数据加入返回 dict：

```python
# 在现有解析逻辑之后新增:
metrics = {"likes": 0, "comments": 0, "shares": 0, "plays": 0, "collects": 0}
m = re.search(r'METRICS:(\{.+?\})', stdout_full)
if m:
    try:
        raw = json.loads(m.group(1))
        metrics = {
            "likes": raw.get("digg_count", 0),
            "comments": raw.get("comment_count", 0),
            "shares": raw.get("share_count", 0),
            "plays": raw.get("play_count", 0),
            "collects": raw.get("collect_count", 0),
        }
    except (json.JSONDecodeError, KeyError):
        pass

return {
    "video_id": actual_video_id,
    "title": title,
    "platform": platform,
    "url": url,
    "filename": filename,
    "file_size_mb": size_mb,
    "metrics": metrics,          # 新增
}
```

### 3.3 `server/handlers/pipeline.py` — 管道保存

**文件**：[pipeline.py](file:///g:/video-analysis-toolkit/server/handlers/pipeline.py)

**改动位置**：`_save_to_library()` 函数，第 274 行。

**现状**：`"metrics": {}`

**改动**：从 downloader 返回的 `info` 中读取 metrics：

```python
"metrics": info.get("metrics", {"likes": 0, "comments": 0, "shares": 0, "plays": 0, "collects": 0}),
```

### 3.4 `scripts/crawl_user_videos.py` — 批量爬取（可选优化）

**文件**：[crawl_user_videos.py](file:///g:/video-analysis-toolkit/scripts/crawl_user_videos.py)

**改动位置**：`get_user_video_ids_via_playwright()` 函数，第 88-100 行。

**现状**：
```python
for v in data.get('aweme_list', []):
    vid = v.get('aweme_id')
    if vid and vid not in seen_ids:
        seen_ids.add(vid)
        desc = v.get('desc', '')
        all_videos.append((vid, desc))
```

**改动**（可选，不影响本次核心需求）：将 `statistics` 一并提取：

```python
stats = v.get('statistics', {})
all_videos.append((vid, desc, stats))
```

### 3.5 `server/handlers/import_video.py` — 本地导入

**文件**：[import_video.py](file:///g:/video-analysis-toolkit/server/handlers/import_video.py)

**改动位置**：第 82 行。

**现状**：`"metrics": {"likes": 0, "comments": 0, "shares": 0, "collects": 0}`

**改动**：新增 `"plays": 0` 保持与 pipeline 结构一致：

```python
"metrics": {"likes": 0, "comments": 0, "shares": 0, "plays": 0, "collects": 0},
```

### 3.6 批量刷新现有视频（新增 API）

**新增接口**：`POST /api/refresh-metrics`

用于对 library.json 中已有的视频批量补抓互动数据。

**请求体**：
```json
{
  "video_ids": ["7646445739824008486", "7664552514141965568"]  // 可选，不传则全部
}
```

**处理逻辑**：
1. 遍历目标视频列表，对平台为 `douyin` 的视频
2. 访问 `https://www.iesdouyin.com/share/video/{video_id}/`
3. 从 HTML 中解析 `statistics` 对象
4. 更新 `library.json` 中对应视频的 `metrics` 字段
5. 返回刷新结果

**响应**：
```json
{
  "status": "done",
  "total": 6,
  "updated": 5,
  "failed": 1,
  "details": [
    {"video_id": "7646445739824008486", "status": "updated", "metrics": {"likes": 14200, ...}},
    {"video_id": "7667951148321475850", "status": "failed", "error": "statistics not found"}
  ]
}
```

### 3.7 前端适配

**文件**：[video-card.js](file:///g:/video-analysis-toolkit/web/js/components/video-card.js) / [library.js](file:///g:/video-analysis-toolkit/web/js/views/library.js)

**改动**：
1. 视频卡片中展示点赞数（已有排序逻辑，数据到位后自动生效）
2. 统计面板的 `total_likes` / `avg_likes` 将自动有真实数据
3. 可在 pipeline 进度卡片中展示实时获取到的 metrics

**新增 UI**：在"添加视频"或视频库工具栏中增加一个"刷新互动数据"按钮，触发 `POST /api/refresh-metrics`。

## 4. 实现优先级

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | vdl.py 解析 statistics 并通过 stdout 输出 | 核心数据源 |
| **P0** | downloader.py 解析 METRICS 行并入返回 dict | 数据传输 |
| **P0** | pipeline.py 将 metrics 写入 library.json | 数据持久化 |
| **P1** | import_video.py 补充 plays 字段 | 结构对齐 |
| **P1** | POST /api/refresh-metrics 接口 | 补抓已有视频 |
| **P2** | 前端视频卡片展示点赞数 | UI 激活 |
| **P2** | 工具栏加"刷新互动数据"按钮 | 手动触发 |
| **P3** | crawl_user_videos.py 提取 statistics | 批量场景优化 |

## 5. 风险与边界

| 风险 | 应对 |
|------|------|
| statistics 正则提取失败 | 静默降级，metrics 保持初始值，不阻塞下载 |
| API 限流 | refresh 接口逐视频请求，间隔 1-2s |
| 非抖音平台不支持 | 仅对 `platform=douyin` 执行，其他平台 metrics 留空 |
| 视频已删除/下架 | 访问 iesdouyin 页面返回空时标记 `failed`，不影响其他视频 |

## 6. 改动文件汇总

```
scripts/vdl.py                     # +解析 statistics 并 stdout 输出 METRICS
server/services/downloader.py      # +解析 METRICS 行，映射字段
server/handlers/pipeline.py        # +从 info 读取 metrics 写入 library
server/handlers/import_video.py    # +补充 plays 字段
server/handlers/refresh_metrics.py # 新建：批量刷新 API
server/server.py                   # +注册 /api/refresh-metrics 路由
web/js/views/library.js            # +工具栏刷新按钮 + 视频卡片展示
```

---

> **下一手**：请 @system-architect-guardian 基于本 PRD 审查向后兼容性、确认正则提取策略的鲁棒性，并输出开发任务拆分。
