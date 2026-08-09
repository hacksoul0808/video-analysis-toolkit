# 视频文案分析平台 — 实现计划与缺口修复

> **日期**: 2026-08-09
> **状态**: 待开发
> **依据**: [PRD-VideoAnalyzer.md](file:///g:/video-analysis-toolkit/Docs/Design/PRD-VideoAnalyzer.md) + `server.py` + `analyzer.html` 代码审查

---

## 概述

对照 PRD 与实际代码（`server.py` + `analyzer.html`），梳理出以下 **16 项功能缺口**，按「面向 C 端用户」标准分为 7 个实现步骤（Step 1 ~ Step 7），每步确保功能闭环、断点可续、UI 状态全覆盖。

---

## 缺口全量清单

| # | 缺口 | 严重程度 | PRD 章节 | 代码现状 |
|---|------|----------|----------|----------|
| 1 | 断点续做（继续转写/继续分析按钮） | 🔴 阻断 | 6.2 | 无 UI 入口 |
| 2 | 转写进度无实时反馈 | 🔴 阻断 | 5.2 | download 有进度，transcribe 无 |
| 3 | 删除视频无 UI | 🔴 阻断 | — | POST /api/delete 已实现，无前端 |
| 4 | 视频详情无自动播放 | 🟡 体验 | 4.2 | video 标签无 autoplay |
| 5 | 重新转写 / 重新分析无入口 | 🟡 体验 | — | 已分析过的无法再触发 |
| 6 | 编辑视频元数据（标题/标签） | 🟡 体验 | 5.6 | POST /api/save 已实现，无前端 |
| 7 | 批量队列模式无前端 | 🟡 体验 | 6.3 | POST /api/batch-analyze 已实现 |
| 8 | AI 分析进度为假进度条 | 🟡 体验 | 5.3 | setInterval 模拟，无真实进度 |
| 9 | 标签管理（添加/编辑/删除标签） | 🟡 体验 | 3.2 | GET /api/tags 已实现，只读 |
| 10 | 下载进度 URL 参数 `?video_id=` 映射问题 | 🟡 可靠性 | 5.1 | pollProgress 用 tempId，与 server 不同步 |
| 11 | 详情弹窗无工作流状态栏 | 🟡 体验 | 4.2 | 只有 data-status 文字，无可视化流水线 |
| 12 | 空状态 / 加载状态不全 | 🟡 体验 | 4.1 | 部分视图有空态，但切换阶段无 loading |
| 13 | 错误重试机制缺失 | 🟡 可靠性 | — | 错误弹窗只有"知道了"，无重试按钮 |
| 14 | 复制报告 / 导出数据 | 🟢 增强 | — | 无任何导出功能 |
| 15 | 视频搜索 / 全文搜索 | 🟢 增强 | — | 无搜索框 |
| 16 | 导入已有视频（非 pipeline 下载的） | 🟢 增强 | — | vdl.py 下载的不在 library 目录 |

---

## Step 1: 基础可用性 — 断点续做 + 完整 CRUD

> **目标**: 用户在任意阶段中断后，重新打开都能看到「继续」按钮，且可编辑/删除。

### 1.1 详情弹窗工作流状态栏

在详情 Modal 中新增可视化流水线指示器（类似 `web_demo/app.py` 已实现的 workflow-bar）：

```
[✅ 下载] → [⬜ 转写 (可点击)] → [⬜ 分析 (条件未满足)]
[✅ 下载] → [✅ 转写] → [⬜ 分析 (可点击)]
[✅ 下载] → [✅ 转写] → [✅ 分析]
```

**修改文件**: `analyzer.html`
- 在 `detail-meta` 与 `detail-tabs` 之间插入 `.workflow-bar`
- 每个阶段的状态由 `v.transcript_status` / `v.deepseek_status` 决定
- **待处理阶段高亮为蓝色**，点击可直接触发该阶段

### 1.2 断点续做按钮

详情弹窗底部新增「操作区」一行按钮，根据当前视频状态动态显示：

| 状态 | 显示按钮 |
|------|---------|
| 仅有文件、未转写 | `[转写]` |
| 已转写、未分析 | `[AI分析]` |
| 已分析 | `[重新分析]` `[重新转写]` |
| 全部未开始 | `[转写]` |
| 转写失败 | `[重试转写]` |

**修改文件**: `analyzer.html`（前端） + `server.py`（需新增 POST /api/transcribe 的独立触发）

### 1.3 删除视频

视频库卡片增加删除操作：
- 卡片右上角 hover 时显示 `×` 删除按钮
- 弹窗确认后调用 POST /api/delete
- 同时删除 library 中的 JSON 记录和 `library/videos/{id}/` 目录

**修改文件**: `analyzer.html` + `server.py`

### 1.4 编辑视频元数据

详情弹窗中标题和标签可编辑：
- 标题支持点击编辑（inline editing）
- 标签支持添加/删除（点击 `+` 新增、点击 `×` 删除）
- 调用 POST /api/save 持久化

**修改文件**: `analyzer.html`

### 1.5 视频自动播放

详情弹窗打开时自动播放视频：
- video 标签增加 `autoplay playsinline`
- `openDetail` 中 `video.play()` 调用

**修改文件**: `analyzer.html`

---

## Step 2: 进度系统 — 真实进度传递

> **目标**: 下载和转写都有实时进度条，不是假进度。

### 2.1 修复下载进度映射

**根因**: 前端生成 `tempId='task_'+Date.now()`，server 管道用 `tempId` 下载，但下载后 video_id 可能不同（如抖音返回真实 ID），导致 pollProgress 找不到正确的进度 key。

**修复方案**:
1. 前端调用 `/api/process` 时，server 返回 `{status: "processing", task_id: "..."}`
2. 前端用 task_id 轮询 `/api/progress?task_id=xxx`
3. Server 内部维护 `task_id → {percent, status, current_step}` 映射
4. 下载完成后 server 返回真实 `video_id`

**修改文件**: `server.py` + `analyzer.html`

### 2.2 转写进度

**方案 A（推荐）**: 在 `transcribe_video_file` 中，faster-whisper 的 `transcribe()` 返回一个 generator。改为分段回调：

```python
# server.py 新增
from threading import Thread

def transcribe_with_progress(video_path, output_path, task_id):
    progress_store[task_id] = {"percent": 0, "status": "transcribing", "current_step": "transcribe"}
    
    model = WhisperModel(...)
    segments_iter = model.transcribe(...)
    
    # faster-whisper 不直接报告进度，但可以从 segment 推断
    for seg in segments_iter:
        segments.append(seg)
        # 基于时间进度估算
        pct = min(int(seg.end / info.duration * 100), 99) if info.duration > 0 else 50
        progress_store[task_id] = {"percent": pct, "status": "transcribing", "current_step": "transcribe"}
    
    progress_store[task_id] = {"percent": 100, "status": "done", "current_step": "transcribe"}
```

**修改文件**: `server.py`

### 2.3 前端进度条组件

统一进度组件，支持 3 种进度源：
- 下载进度（来自 vdl.py 的 PROGRESS:xx 输出）
- 转写进度（来自 server 分段回调）
- AI 分析进度（DeepSeek API 调用中，一般为不可细分，显示 spinner）

**修改文件**: `analyzer.html`

---

## Step 3: 交互闭环 — 正常/空/异常/加载四态

> **目标**: 每个 UI 区域都有完整的状态覆盖，不给用户看到空白或断裂。

### 3.1 四态规范

每个视图必须覆盖的 4 个状态：

| 状态 | 触发条件 | UI 表现 |
|------|---------|---------|
| **正常态** | 数据存在且已就绪 | 展示数据 |
| **空态** | 无数据 | 插画 + 引导文案 + CTA 按钮 |
| **加载态** | 正在请求中 | Skeleton / Shimmer / Spinner |
| **异常态** | 请求失败 / 步骤失败 | 错误信息 + 重试按钮 |

### 3.2 各区域状态检查清单

| 区域 | 正常 | 空 | 加载 | 异常 | 当前缺 |
|------|------|-----|------|------|--------|
| 视频库 Grid | ✅ | ✅ | ❌ | ❌ | 加载+异常 |
| 添加弹窗 Pipeline | ✅ | — | ✅ | ✅ | OK |
| 详情弹窗-转写tab | ✅ | ✅ | ❌ | ❌ | 加载+异常 |
| 详情弹窗-指标tab | ✅ | ✅ | ❌ | ❌ | 加载+异常 |
| 详情弹窗-分析tab | ✅ | ✅ | ❌ | ❌ | 加载+异常 |
| 方法论视图 | ✅ | ✅ | ❌ | ❌ | 加载+异常 |
| 统计视图 | ✅ | ✅ | ❌ | ❌ | 加载+异常 |

**修改文件**: `analyzer.html`

### 3.3 错误重试

所有异常态都需包含「重试」按钮，点击后重新发起请求。
- 转写/分析失败：重试按钮调用 POST /api/transcribe 或 POST /api/analyze
- 网络错误：重试按钮重新 fetch

---

## Step 4: 标签体系 — 从只读到可管理

> **目标**: 标签不仅仅是分类展示，要支持增删改。

### 4.1 标签管理面板

在视频库视图的 tag-cloud 区域增加「管理标签」按钮，点击展开标签管理面板：
- 列表展示所有标签及使用次数
- 支持重命名（合并标签）
- 支持删除（解绑该标签下所有视频）
- 支持合并（将 A 标签合并到 B 标签）

### 4.2 视频详情中的标签编辑

详情弹窗中标签区域改为可编辑：
- 点击已有标签 → 删除
- 输入框 + 自动补全 → 添加
- 实时保存到 server

**修改文件**: `analyzer.html` + `server.py`（新增 PUT /api/tags 端点）

---

## Step 5: 批量模式

> **目标**: 支持多 URL 批量入队 + 一键批量分析。

### 5.1 批量添加

添加弹窗增加批量模式开关：
- 单 URL 模式（现有）
- 多 URL 模式（textarea，每行一个链接）
- 提交后展示队列列表，每项显示进度

### 5.2 批量分析

视频库卡片增加多选模式（批量选择按钮）：
- 勾选多个视频 → 「批量AI分析」按钮
- 调用 POST /api/batch-analyze
- 返回每个视频的分析结果

**修改文件**: `analyzer.html`（主要是前端）

---

## Step 6: AI 分析细节增强

> **目标**: AI 分析不是一次性动作，支持重新生成、自定义 prompt。

### 6.1 真实进度（非假进度条）

DeepSeek API 调用通常是几秒到十几秒，无法实时进度。改为：
- 显示 waiting → thinking → done 三阶段文案动画
- 可展示实际耗时
- 如果超时（> 60s），显示警告

### 6.2 重新分析确认

「重新分析」按钮点击时：
- 弹窗确认（"将覆盖现有分析报告，确定？"）
- 执行后更新报告和爆款分
- 保留历史报告（追加时间戳文件名）

### 6.3 报告导出

AI 分析报告支持：
- 复制为 Markdown（一键复制按钮）
- 下载为 .md 文件

**修改文件**: `analyzer.html` + `server.py`

---

## Step 7: 搜索与导入

> **目标**: 视频多了需要搜索，手动下载的视频能导入。

### 7.1 搜索

视频库顶部增加搜索框：
- 搜索标题/转写文本
- 后端新增 GET /api/library?q=xxx 全文搜索
- 从 transcript.json 中匹配

**修改文件**: `analyzer.html` + `server.py`

### 7.2 导入已有视频

对于通过 vdl.py 直接下载的视频：
- 新增「导入视频」功能
- 选择 `videos/` 目录中的 mp4 文件
- 自动关联到 library

实际上更简单的方案：server 提供 GET /api/library 时自动扫描非 library 目录的视频文件。或者在添加弹窗中增加「从本地导入」选项。

**修改文件**: `analyzer.html` + `server.py`

---

## 开发依赖图

```
Step 1 (基础可用性) ←── 必须最先做
  │
  ├── Step 2 (进度系统) ←── 可与 Step 1 并行
  │
  ├── Step 3 (四态覆盖) ←── 依赖 Step 1 的 UI 结构
  │
  ├── Step 4 (标签管理) ←── 依赖 Step 1
  │
  ├── Step 5 (批量模式) ←── 独立
  │
  ├── Step 6 (AI 增强) ←── 独立
  │
  └── Step 7 (搜索导入) ←── 独立
```

**推荐执行顺序**: Step 1 → Step 3 → Step 2 → Step 4 → Step 5 → Step 6 → Step 7

---

## 验收检查清单

每步完成后，按以下清单自测：

### Step 1 验收
- [ ] 库中视频 card 上 hover 出现删除 `×` 按钮，点击可删除
- [ ] 详情弹窗顶部有 `[下载✅] [转写⬜] [分析⬜]` 工作流状态栏
- [ ] 仅下载未转写的视频，详情中显示「开始转写」按钮
- [ ] 已转写未分析的视频，详情中显示「AI 分析」按钮
- [ ] 已全部分析的视频，详情中显示「重新分析」+「重新转写」
- [ ] 标题可点击编辑，回车保存
- [ ] 标签可添加/删除
- [ ] 视频自动播放

### Step 2 验收
- [ ] 下载进度条从 0% → 100%，无卡死
- [ ] 转写过程显示实时百分比
- [ ] 进度数字与 server 端输出一致

### Step 3 验收
- [ ] 视频库首次加载显示 shimmer 骨架屏
- [ ] 请求失败显示错误信息 + 重试按钮
- [ ] 转写 tab 加载中显示 spinner
- [ ] 分析 tab 加载中显示进度动画

### Step 4 验收
- [ ] 标签可重命名
- [ ] 重命名后所有相关视频同步更新
- [ ] 标签可删除
- [ ] 视频详情中标签可自由编辑

### Step 5 验收
- [ ] 批量输入 3 个 URL，全部入队
- [ ] 队列中每个显示独立进度
- [ ] 批量分析全部完成后统一展示

### Step 6 验收
- [ ] AI 分析显示真实等待状态（非假进度）
- [ ] 重新分析前弹出确认
- [ ] 报告可一键复制
- [ ] 报告可下载为 .md

### Step 7 验收
- [ ] 搜索"Transformer"可匹配到包含该词的视频
- [ ] 可导入 `videos/` 目录中已有视频到 library

---

> **下一步**: 从 Step 1 开始逐步实现，每完成一步验收后再进行下一步。
