# 产品需求文档：视频文案分析平台 (Video Script Analyzer)

> **版本**: v1.0  
> **日期**: 2026-08-09  
> **状态**: 待开发  

---

## 1. 产品概述

### 1.1 一句话描述
输入视频链接 → 自动下载 + 转写 + DeepSeek AI 分析 → 输出爆款方法论，所有数据本地持久化。

### 1.2 核心价值
- **闭环流水线**：从 URL 到分析报告，全自动或按需触发
- **可复制的方法论**：不止看数据，DeepSeek 提取可落地的文案模板
- **本地优先**：一切数据存在本地 JSON 文件，无需云服务
- **标签体系**：AI 自动分类，建立个人爆款视频知识库

### 1.3 用户画像
内容创作者/运营人员，需要系统性分析热门视频的文案策略，建立可复用的方法论库。

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────┐
│  前端 SPA (单 HTML 文件: analyzer.html)           │
│  ├── 首页仪表盘 (视频库概览 + 统计)                │
│  ├── 添加视频 (URL 输入 → 流水线状态)             │
│  ├── 视频详情 (播放 + 转写 + AI 分析报告)         │
│  ├── 标签管理 (筛选 / 聚合统计)                   │
│  └── 方法论库 (按标签/模式聚合的文案策略)          │
├─────────────────────────────────────────────────┤
│  Python API 服务器 (server.py, ~400行)            │
│  ├── GET  /              → 提供 SPA HTML         │
│  ├── POST /api/download  → 调用 vdl.py           │
│  ├── POST /api/transcribe→ 调用 transcribe_videos│
│  ├── POST /api/analyze   → 调用 DeepSeek API     │
│  ├── GET  /api/library   → 读取 library.json     │
│  ├── POST /api/video/save→ 写入 library.json     │
│  └── GET  /api/stats     → 聚合统计              │
├─────────────────────────────────────────────────┤
│  本地存储 (JSON 文件)                              │
│  ├── library/library.json     → 视频索引库        │
│  ├── library/videos/{id}/     → 每个视频目录       │
│  │   ├── video.mp4            → 原始视频          │
│  │   ├── transcript.json      → 转写文本          │
│  │   ├── analysis.json        → 脚本分析          │
│  │   └── deepseek_report.md   → AI 分析报告       │
│  └── library/tags.json        → 标签体系           │
└─────────────────────────────────────────────────┘
```

### 2.2 技术选型

| 层级 | 技术 | 理由 |
|------|------|------|
| 前端 | 原生 HTML/CSS/JS (单文件) | 个人工具、零依赖、苹果风格毛玻璃 UI |
| 图表 | Chart.js (CDN) | 与现有仪表盘一致 |
| 后端 | Python `http.server` | 最小化依赖，与现有代码一致 |
| 下载 | `vdl.py` / `yt-dlp` | 复用现有模块 |
| 转写 | `faster-whisper large-v3` | 复用现有模块 |
| AI 分析 | DeepSeek API (Chat Completions) | 性价比最高的中文 LLM |
| 存储 | JSON 文件 + 本地目录 | 可读可编辑，符合个人工具定位 |

### 2.3 端口
- 默认端口: `8840` (不与现有 `8300` 冲突)

---

## 3. 数据模型

### 3.1 library.json（视频索引库）

```json
{
  "videos": [
    {
      "id": "7478499889047260476",
      "url": "https://v.douyin.com/xxx/",
      "platform": "douyin",
      "title": "颠覆10年共识！马斯克叹服！",
      "author": "博主名",
      "duration_sec": 358,
      "file_size_mb": 45.2,
      "download_time": "2026-08-09T12:00:00Z",
      "transcript_status": "done",
      "analysis_status": "done",
      "deepseek_status": "done",
      "tags": ["论文精读", "AI", "颠覆性结论"],
      "metrics": {
        "likes": 14200,
        "comments": 890,
        "shares": 3200,
        "collects": 6300
      },
      "script_stats": {
        "char_count": 1820,
        "chars_per_min": 305,
        "ai_keywords": 12,
        "emotion_keywords": 7,
        "tech_keywords": 5,
        "keyword_density": 2.6
      },
      "viral_score": 92,
      "created_at": "2026-08-09T12:00:00Z"
    }
  ],
  "updated_at": "2026-08-09T20:00:00Z"
}
```

### 3.2 tags.json（标签体系）

```json
{
  "tags": [
    {
      "name": "论文精读",
      "count": 8,
      "avg_likes": 4270,
      "avg_viral_score": 78,
      "common_patterns": ["认知颠覆钩子", "权威背书", "5-8分钟"]
    }
  ],
  "categories": ["内容类型", "平台", "情绪调性", "时长区间", "爆款等级"]
}
```

### 3.3 deepseek_report.md（AI 分析报告）

每个视频的 AI 报告包含 5 个模块（对应 Q4 全选 ABCDE）：

```markdown
# AI 文案分析报告: 《颠覆10年共识！马斯克叹服！》

## 🎯 爆款公式拆解
- **开场钩子类型**: 认知颠覆型 (0-8s)
- **情绪节奏**: 惊讶→好奇→兴奋→满足 (4段式)
- **信息密度曲线**:
  0-60s  ████████░░  高密度核心观点
  60-180s ██████░░░░  案例展开
  180-end  ████░░░░░░  总结+引导收藏
- **标题策略**: [权威人物] + [颠覆性形容词] + [感叹号]
  → 模板: "{名人}也{震惊/叹服/承认}！{核心结论}"
- **引导转化**: 结尾引导收藏 ("建议收藏慢慢消化")

## 📋 可复制模板
### 标题模板
> 「{行业大事件}」刚发生，{权威来源}的结论让所有人意外：[核心观点]
### 结构模板
1. **Hook (0-8s)**: "{事实陈述}是错的。{一句话颠覆认知}"
2. **Why (8-30s)**: "为什么？因为{2-3个关键论据}"
3. **How (30-300s)**: "{案例/数据}证明，具体来说..."
4. **CTA (最后15s)**: "建议{收藏/转发}，{一句话价值总结}"

## 📊 同类对比
| 指标 | 本视频 | 平台均值 | 差异 |
|------|--------|---------|------|
| 收藏/赞比 | 44.4% | 12% | +32.4% ↑ |
| 分享/赞比 | 22.5% | 8% | +14.5% ↑ |
| 语速 | 305字/分 | 280字/分 | +8.9% |
| 情绪词 | 7个 | 3个 | +133% ↑ |

## 🔧 改进建议
1. **标题可缩短**：当前28字，建议压缩到18字以内提高完读率
2. **3-5分钟段落太长**：可插入一个"悬念问题"在第3分钟处制造二次钩子
3. **缺少视觉引导词**：可加入"看这张图""注意这里"等引导观众注意力的话术

## 🏷️ 自动标签
`#论文精读` `#AI` `#颠覆性结论` `#深度学习` `#收藏向` `#5-8分钟`
```

---

## 4. 页面与 UI 设计

### 4.1 页面结构（单页 SPA，3 个视图切换）

```
┌──────────────────────────────────────────────────┐
│  🔬 Video Script Analyzer    [添加视频] [标签]    │
├──────────────────────────────────────────────────┤
│  ┌─ Tab: 视频库 ──────────────────────────────┐  │
│  │  [全部] [论文精读] [产品测评] [行业热点] ...  │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐          │  │
│  │  │ 视频卡片│ │ 视频卡片│ │ 视频卡片│  ...     │  │
│  │  │ 缩略图  │ │ 缩略图  │ │ 缩略图  │          │  │
│  │  │ 标题    │ │ 标题    │ │ 标题    │          │  │
│  │  │ 标签    │ │ 标签    │ │ 标签    │          │  │
│  │  │ ⭐92分  │ │ ⭐78分  │ │ ⭐55分  │          │  │
│  │  └────────┘ └────────┘ └────────┘          │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  ┌─ Tab: 方法论库 ───────────────────────────┐   │
│  │  按标签聚合的爆款公式卡片                    │   │
│  │  "论文精读"类 → 4种开场钩子 → 3套标题模板  │   │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  ┌─ Tab: 统计看板 ───────────────────────────┐   │
│  │  Chart.js 图表: 标签分布/爆款分/时长-点赞  │   │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 4.2 视频详情弹窗（Modal）

```
┌──────────────────────────────────────────────────┐
│  ×                                          [X]  │
│  ┌─────────────────────────────┐                 │
│  │       视频播放器             │                 │
│  └─────────────────────────────┘                 │
│  标题: 颠覆10年共识！马斯克叹服！                  │
│  ┌─ Tabs ────────────────────────────────────┐   │
│  │ [转写文本] [脚本指标] [AI爆款分析]         │   │
│  ├───────────────────────────────────────────┤   │
│  │ (对应 tab 内容，AI分析渲染为 Markdown)     │   │
│  └───────────────────────────────────────────┘   │
│  标签: #论文精读 #AI #颠覆性结论  [编辑标签]     │
│  ⭐ 爆款指数: 92/100                             │
└──────────────────────────────────────────────────┘
```

### 4.3 添加视频浮层

```
┌──────────────────────────────────────────────────┐
│  添加视频分析                                     │
│  ┌──────────────────────────────────────────┐    │
│  │ 粘贴视频链接...                           │    │
│  └──────────────────────────────────────────┘    │
│  ○ 仅下载 + 转写                                 │
│  ● 下载 + 转写 + AI 分析（全自动）               │
│  ○ 加入批量队列（稍后统一分析）                   │
│  [开始分析]                                       │
│                                                   │
│  ┌─ 进度 ───────────────────────────────────┐    │
│  │ ✅ 下载完成 (45.2 MB)                     │    │
│  │ ✅ 转写完成 (1,820 字)                    │    │
│  │ 🔄 AI 分析中...                           │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### 4.4 视觉风格
- **主题**: 深色模式，苹果毛玻璃 (Glassmorphism)
- **配色**: 背景 `#0f0f1a`，主色 `#7c9ff5`，强调 `#e94560`
- **卡片**: `backdrop-filter: blur()` + 半透明背景 + 圆角 `12px`
- 与现有 `web_demo/app.py` 仪表盘风格保持统一

---

## 5. API 端点设计

### 5.1 下载视频
```
POST /api/download
Body: { "url": "https://v.douyin.com/xxx/", "mode": "auto" }
Response: { "status": "done", "video_id": "xxx", "file_path": "...", "title": "...", "duration": 358, "platform": "douyin", "size_mb": 45.2 }
```

### 5.2 转写视频
```
POST /api/transcribe
Body: { "video_id": "xxx" }
Response: { "status": "done", "char_count": 1820, "segment_count": 68, "duration_sec": 358, "language": "zh" }
```

### 5.3 AI 分析（调用 DeepSeek）
```
POST /api/analyze
Body: { "video_id": "xxx", "mode": "on_demand" }
Response: { "status": "done", "viral_score": 92, "report": "(Markdown)", "tags": ["论文精读", "AI", ...] }
```

### 5.4 批量队列分析
```
POST /api/batch-analyze
Body: { "video_ids": ["id1", "id2", "id3"] }
Response: { "status": "queued", "total": 3 }
```

### 5.5 获取视频库
```
GET /api/library?tag=AI&sort=likes&page=1
Response: { "videos": [...], "total": 25, "tags": [...] }
```

### 5.6 获取统计聚合
```
GET /api/stats
Response: { "total_videos": 25, "by_tag": {...}, "avg_viral_score": 68, "top_patterns": [...] }
```

### 5.7 获取方法论聚合
```
GET /api/methodology?tag=论文精读
Response: { "patterns": [...], "templates": [...], "best_examples": [...] }
```

---

## 6. 核心流程

### 6.1 全自动流水线（模式 B）
```
用户输入 URL
  → POST /api/download    (复用 vdl.py)
  → POST /api/transcribe  (复用 transcribe_videos.py)
  → POST /api/analyze     (调用 analyze_scripts.py + DeepSeek API)
  → 保存到 library/
  → 前端刷新展示
```

### 6.2 按需触发（模式 A）
```
用户输入 URL
  → POST /api/download
  → POST /api/transcribe
  → 前端展示 [AI分析] 按钮
  → 用户点击 → POST /api/analyze
```

### 6.3 批量模式（模式 C）
```
用户输入多个 URL（或选中库中已有视频）
  → POST /api/batch-queue  (加入队列)
  → 批量下载 + 转写（可并行）
  → 用户点击 [一键批量分析]
  → 顺序调用 DeepSeek API
  → 全部完成后生成对比报告
```

---

## 7. DeepSeek Prompt 工程规范

### 7.1 System Prompt

```
你是一位顶级短视频文案分析师，曾服务于头部 MCN 机构。你的任务是深度分析视频转写文案，
输出可直接落地的爆款方法论。

分析时必须严格遵循以下结构输出 Markdown：

## 🎯 爆款公式拆解
- 开场钩子类型（恐惧/认知颠覆/数据冲击/反直觉，四选一）
- 情绪节奏曲线（标注时间节点）
- 信息密度分布（高/中/低 + 时间区间）
- 标题公式提取（给出可复用的模板）

## 📋 可复制模板
- 标题模板（含 {占位符}）
- 结构模板（Hook-Why-How-CTA 或自定义）

## 📊 同类对比分析
仅基于提供的参考数据对比（收藏率/分享率/语速/情绪词），给出差异化分析

## 🔧 改进建议
3 条具体可执行的优化建议（标题/节奏/话术）

## 🏷️ 自动标签
从预设标签库中选择 3-5 个最匹配的标签，格式: `#标签1 #标签2`

标签库: 论文精读, 行业热点, 产品测评, 商务合作, 科普教程, 教程向, 
收藏向, 传播向, AI, 深度学习, 颠覆性结论, 数据驱动, 认知升级, 
实用技巧, 3分钟以内, 5-8分钟, 10分钟以上, 爆款, 优质, 普通
```

### 7.2 User Prompt 模板

```
分析以下短视频文案，参考数据：
- 时长: {duration}秒
- 总字数: {char_count}
- 语速: {chars_per_min}字/分钟
- 点赞: {likes}
- 收藏/赞比: {collect_rate}%
- 分享/赞比: {share_rate}%
- 情绪词数量: {emotion_count}
- 关键词密度: {keyword_density}%
- 平台: {platform}
- 博主: {author}

开场(前30秒):
{hook_text}

完整转写文本:
{full_text}
```

### 7.3 API 调用参数
```python
{
  "model": "deepseek-chat",
  "temperature": 0.7,
  "max_tokens": 4096,
  "messages": [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_prompt}
  ]
}
```

### 7.4 爆款指数计算

DeepSeek 返回报告后，后端从报告中提取量化指标计算 0-100 分：

```
viral_score = 
  hook_quality      (0-25分: 开场钩子有效性)
+ structure_score   (0-25分: 结构完整度)
+ emotion_density   (0-20分: 情绪词密度)
+ engagement_ratio  (0-15分: 收藏+分享率)
+ template_score    (0-15分: 模板可复用度)
```

---

## 8. 文件结构

```
video-analysis-toolkit/
├── analyzer.html               # 前端 SPA (新建)
├── server.py                   # API 服务器 (新建)
├── vdl.py                      # 视频下载 (复用)
├── transcribe_videos.py        # 语音转写 (复用)
├── analyze_scripts.py          # 脚本分析 (复用)
├── requirements.txt            # 依赖 (更新: +openai)
├── library/                    # 本地数据库 (新建)
│   ├── library.json            # 视频索引
│   ├── tags.json               # 标签体系
│   └── videos/
│       └── {video_id}/
│           ├── video.mp4
│           ├── transcript.json
│           ├── script_analysis.json
│           └── deepseek_report.md
├── Docs/
│   └── Design/
│       └── PRD-VideoAnalyzer.md  # 本文件
└── web_demo/                   # 原仪表盘 (保留)
    └── app.py
```

---

## 9. 开发阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **Phase 1** | `server.py` API 服务 + `analyzer.html` 基础框架（视频库展示+上传） | 现有 vdl.py |
| **Phase 2** | 下载+转写流水线串联，进度实时反馈 | 现有 transcribe_videos.py |
| **Phase 3** | DeepSeek API 集成，AI 分析报告渲染 | DeepSeek API Key |
| **Phase 4** | 标签系统 + 方法论聚合 + 统计看板 | Phase 3 |
| **Phase 5** | 批量模式 + 对比分析 | Phase 4 |

---

## 10. 前置依赖与配置

### 10.1 新增 Python 依赖
```
openai>=1.0          # DeepSeek API 调用（兼容 OpenAI SDK）
```
更新到 `requirements.txt`。

### 10.2 环境变量
```
DEEPSEEK_API_KEY=sk-xxx      # DeepSeek API 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 10.3 硬件要求
- GPU (CUDA): faster-whisper 转写加速（CPU 亦可，较慢）
- 磁盘: 按视频量，每个视频约 30-100MB

---

> **下一手**: 请 @system-architect-guardian 基于本 PRD 设计后端 config 结构、API 详细规范、前端组件树，并输出 Frontend Development Guide。
