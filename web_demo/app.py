#!/usr/bin/env python3
"""
Lau博士的云组会 — 抖音博主分析 Web Demo

Run: cd ~/download_video/web_demo && python app.py
Then open: http://localhost:8765
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

PORT = int(os.environ.get("PORT", 8300))
BASE = Path(__file__).parent
VIDEO_DIR = BASE.parent / "videos" / "lau_all"

# Load data
with open(BASE / "data.json", encoding="utf-8") as f:
    DATA = json.load(f)

VIDEOS = DATA["videos"]
VIDEOS.sort(key=lambda x: x.get("create_time", 0), reverse=True)

# Load transcripts
TRANSCRIPTS = {}
transcript_file = BASE / "all_transcripts.json"
if transcript_file.exists():
    with open(transcript_file, encoding="utf-8") as f:
        TRANSCRIPTS = json.load(f)

# Load script analysis
SCRIPT_ANALYSIS = {}
analysis_file = BASE / "script_analysis.json"
if analysis_file.exists():
    with open(analysis_file, encoding="utf-8") as f:
        SCRIPT_ANALYSIS = json.load(f)

# Map video IDs to files
VID_FILES = {}
if VIDEO_DIR.exists():
    for f in VIDEO_DIR.iterdir():
        if f.suffix == ".mp4":
            m = re.search(r"(\d{18,})", f.name)
            if m:
                VID_FILES[m.group(1)] = f


def build_index_html():
    """Build the main dashboard page."""
    n = len(VIDEOS)
    total_likes = sum(v["digg_count"] for v in VIDEOS)
    total_comments = sum(v["comment_count"] for v in VIDEOS)
    total_shares = sum(v["share_count"] for v in VIDEOS)
    total_collects = sum(v["collect_count"] for v in VIDEOS)
    total_duration = sum(v.get("duration_sec", 0) for v in VIDEOS)
    followers = 77000

    avg_likes = total_likes // n if n else 0
    avg_comments = total_comments // n if n else 0
    avg_shares = total_shares // n if n else 0
    avg_collects = total_collects // n if n else 0
    save_rate = total_collects / total_likes * 100 if total_likes else 0
    share_rate = total_shares / total_likes * 100 if total_likes else 0
    engagement = (total_likes + total_comments) / n / followers * 100 if n and followers else 0

    # Top 5 by likes
    top5 = sorted(VIDEOS, key=lambda x: x["digg_count"], reverse=True)[:5]
    # Bottom 3
    bot3 = sorted(VIDEOS, key=lambda x: x["digg_count"])[:3]

    # Duration buckets
    short = [v for v in VIDEOS if v.get("duration_sec", 0) < 180]
    medium = [v for v in VIDEOS if 180 <= v.get("duration_sec", 0) < 480]
    long_v = [v for v in VIDEOS if v.get("duration_sec", 0) >= 480]

    # Monthly
    from collections import defaultdict, Counter
    monthly = defaultdict(list)
    for v in VIDEOS:
        if v.get("create_time"):
            month = datetime.fromtimestamp(v["create_time"]).strftime("%Y-%m")
            monthly[month].append(v)

    # Categories
    categories = {}
    for v in VIDEOS:
        desc = v["desc"].lower()
        if any(k in desc for k in ["论文", "cvpr", "iclr", "transformer", "vit", "attn", "residual", "mudd", "fars"]):
            cat = "论文精读"
        elif any(k in desc for k in ["开源", "发布", "登顶", "deepseek", "glm", "kimi", "chatgpt"]):
            cat = "行业热点"
        elif any(k in desc for k in ["测评", "测试", "ticnote", "seedance"]):
            cat = "产品测评"
        elif any(k in desc for k in ["豆包", "广告"]):
            cat = "商务合作"
        else:
            cat = "科普教程"
        categories.setdefault(cat, []).append(v)

    # Hashtags
    all_tags = [t for v in VIDEOS for t in v.get("hashtags", [])]
    tag_counts = Counter(all_tags).most_common(10)

    # Build video cards HTML
    video_cards = ""
    for i, v in enumerate(VIDEOS):
        vid = v["id"]
        dt = datetime.fromtimestamp(v["create_time"]).strftime("%Y-%m-%d") if v.get("create_time") else "?"
        dur = v.get("duration_sec", 0)
        dur_str = f"{int(dur//60)}:{int(dur%60):02d}"
        desc_line1 = v["desc"].split("\n")[0][:80]
        has_file = vid in VID_FILES
        has_thumb = (BASE / "thumbnails" / f"{vid}.jpg").exists()

        # Engagement metrics
        save_r = v["collect_count"] / max(v["digg_count"], 1) * 100
        share_r = v["share_count"] / max(v["digg_count"], 1) * 100

        # Performance tier
        if v["digg_count"] >= 10000:
            tier = "tier-hot"
            tier_label = "爆款"
        elif v["digg_count"] >= 3000:
            tier = "tier-good"
            tier_label = "优秀"
        elif v["digg_count"] >= 1000:
            tier = "tier-ok"
            tier_label = "正常"
        else:
            tier = "tier-low"
            tier_label = "低迷"

        thumb_src = f"/thumbnails/{vid}.jpg" if has_thumb else ""
        video_link = f"/video/{vid}" if has_file else "#"

        video_cards += f"""
        <div class="video-card {tier}" data-likes="{v['digg_count']}" data-date="{v.get('create_time',0)}" data-duration="{dur}" onclick="showVideo('{vid}')">
            <div class="thumb-wrapper">
                {'<img class="thumb" src="' + thumb_src + '" alt="thumbnail" loading="lazy">' if has_thumb else '<div class="thumb-placeholder">No Thumb</div>'}
                <span class="duration-badge">{dur_str}</span>
                <span class="tier-badge {tier}">{tier_label}</span>
            </div>
            <div class="card-body">
                <h3 class="card-title">{desc_line1}</h3>
                <div class="card-date">{dt}</div>
                <div class="card-stats">
                    <span class="stat">❤️ {v['digg_count']:,}</span>
                    <span class="stat">💬 {v['comment_count']:,}</span>
                    <span class="stat">🔗 {v['share_count']:,}</span>
                    <span class="stat">⭐ {v['collect_count']:,}</span>
                </div>
                <div class="card-rates">
                    <span class="rate" title="收藏/赞比 (干货程度)">📌 {save_r:.0f}%</span>
                    <span class="rate" title="分享/赞比 (传播力)">📤 {share_r:.0f}%</span>
                    <span class="rate" title="文件大小">{v.get('file_size_mb', '?')} MB</span>
                </div>
            </div>
        </div>
        """

    # Chart data for JS
    monthly_labels = json.dumps(sorted(monthly.keys()))
    monthly_likes = json.dumps([sum(v["digg_count"] for v in monthly[m]) for m in sorted(monthly.keys())])
    monthly_counts = json.dumps([len(monthly[m]) for m in sorted(monthly.keys())])
    monthly_avg = json.dumps([sum(v["digg_count"] for v in monthly[m]) // len(monthly[m]) for m in sorted(monthly.keys())])

    # Duration chart data
    dur_data = []
    for v in VIDEOS:
        dur_data.append({"x": v.get("duration_sec", 0) / 60, "y": v["digg_count"], "title": v["desc"][:30]})
    dur_json = json.dumps(dur_data, ensure_ascii=False)

    # Category chart
    cat_labels = json.dumps(list(categories.keys()), ensure_ascii=False)
    cat_counts = json.dumps([len(v) for v in categories.values()])
    cat_avg_likes = json.dumps([sum(x["digg_count"] for x in v) // len(v) for v in categories.values()])

    # Top 5 chart
    top5_labels = json.dumps([v["desc"][:20] for v in top5], ensure_ascii=False)
    top5_likes = json.dumps([v["digg_count"] for v in top5])
    top5_collects = json.dumps([v["collect_count"] for v in top5])
    top5_shares = json.dumps([v["share_count"] for v in top5])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lau博士的云组会 - 抖音博主分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1a; color: #e0e0e0; }}
a {{ color: #7c9ff5; text-decoration: none; }}

/* Header */
.header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); padding: 32px; text-align: center; border-bottom: 2px solid #e94560; }}
.header h1 {{ font-size: 28px; margin-bottom: 8px; color: #fff; }}
.header .subtitle {{ color: #aaa; font-size: 14px; }}
.header .bio {{ color: #7c9ff5; margin-top: 8px; }}

/* KPI Row */
.kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; padding: 24px 32px; max-width: 1400px; margin: 0 auto; }}
.kpi-card {{ background: #1a1a2e; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #2a2a4a; transition: transform 0.2s; }}
.kpi-card:hover {{ transform: translateY(-2px); border-color: #e94560; }}
.kpi-value {{ font-size: 28px; font-weight: 700; color: #e94560; }}
.kpi-value.blue {{ color: #7c9ff5; }}
.kpi-value.green {{ color: #4ecdc4; }}
.kpi-value.gold {{ color: #ffd700; }}
.kpi-label {{ font-size: 12px; color: #888; margin-top: 4px; }}

/* Insight box */
.insight-box {{ max-width: 1400px; margin: 24px auto; padding: 0 32px; }}
.insight {{ background: linear-gradient(135deg, #1a2a1a 0%, #1a1a2e 100%); border-left: 4px solid #4ecdc4; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; }}
.insight h3 {{ color: #4ecdc4; margin-bottom: 8px; font-size: 16px; }}
.insight p {{ color: #ccc; font-size: 14px; line-height: 1.6; }}
.insight .highlight {{ color: #e94560; font-weight: 600; }}
.insight .good {{ color: #4ecdc4; font-weight: 600; }}

/* Charts */
.charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px; max-width: 1400px; margin: 24px auto; padding: 0 32px; }}
.chart-box {{ background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }}
.chart-box h3 {{ color: #fff; margin-bottom: 16px; font-size: 16px; }}
.chart-box canvas {{ max-height: 300px; }}

/* Section */
.section {{ max-width: 1400px; margin: 32px auto; padding: 0 32px; }}
.section h2 {{ color: #fff; font-size: 22px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e94560; }}

/* Video Grid */
.video-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }}
.video-card {{ background: #1a1a2e; border-radius: 12px; overflow: hidden; border: 1px solid #2a2a4a; cursor: pointer; transition: all 0.3s; }}
.video-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 24px rgba(233,69,96,0.2); border-color: #e94560; }}
.video-card.tier-hot {{ border-left: 4px solid #e94560; }}
.video-card.tier-good {{ border-left: 4px solid #ffd700; }}
.video-card.tier-ok {{ border-left: 4px solid #4ecdc4; }}
.video-card.tier-low {{ border-left: 4px solid #555; }}

.thumb-wrapper {{ position: relative; aspect-ratio: 16/9; background: #0a0a15; overflow: hidden; }}
.thumb {{ width: 100%; height: 100%; object-fit: cover; }}
.thumb-placeholder {{ display: flex; align-items: center; justify-content: center; height: 100%; color: #555; }}
.duration-badge {{ position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.8); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.tier-badge {{ position: absolute; top: 8px; left: 8px; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.tier-badge.tier-hot {{ background: #e94560; color: #fff; }}
.tier-badge.tier-good {{ background: #ffd700; color: #000; }}
.tier-badge.tier-ok {{ background: #4ecdc4; color: #000; }}
.tier-badge.tier-low {{ background: #555; color: #fff; }}

.card-body {{ padding: 12px 16px; }}
.card-title {{ font-size: 14px; color: #fff; margin-bottom: 6px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.card-date {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
.card-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }}
.stat {{ font-size: 13px; color: #aaa; }}
.card-rates {{ display: flex; gap: 12px; }}
.rate {{ font-size: 11px; color: #666; }}

/* Sort/Filter bar */
.controls {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }}
.controls select, .controls button {{ background: #2a2a4a; color: #e0e0e0; border: 1px solid #3a3a5a; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; }}
.controls button.active {{ background: #e94560; border-color: #e94560; }}
.controls button:hover {{ border-color: #e94560; }}

/* Video modal */
.modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; overflow-y: auto; }}
.modal.show {{ display: flex; justify-content: center; align-items: flex-start; padding: 40px 20px; }}
.modal-content {{ background: #1a1a2e; border-radius: 16px; max-width: 900px; width: 100%; overflow: hidden; }}
.modal-video {{ width: 100%; aspect-ratio: 16/9; background: #000; }}
.modal-info {{ padding: 24px; }}
.modal-info h2 {{ color: #fff; font-size: 18px; margin-bottom: 12px; line-height: 1.5; }}
.modal-stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; }}
.modal-stat {{ text-align: center; }}
.modal-stat .val {{ font-size: 24px; font-weight: 700; }}
.modal-stat .lbl {{ font-size: 11px; color: #888; }}
.modal-close {{ position: fixed; top: 20px; right: 30px; color: #fff; font-size: 32px; cursor: pointer; z-index: 1001; background: rgba(0,0,0,0.5); width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }}

/* Strategy section */
.strategy {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a4a; }}
.strategy h3 {{ color: #e94560; margin-bottom: 12px; }}
.strategy ul {{ list-style: none; padding: 0; }}
.strategy li {{ padding: 8px 0; border-bottom: 1px solid #2a2a4a; font-size: 14px; line-height: 1.6; }}
.strategy li:last-child {{ border: none; }}
.strategy .do {{ color: #4ecdc4; }}
.strategy .dont {{ color: #e94560; }}

/* Tabs */
.modal-tabs {{ display: flex; gap: 8px; margin-bottom: 16px; }}
.tab-btn {{ background: #2a2a4a; color: #aaa; border: 1px solid #3a3a5a; padding: 8px 20px; border-radius: 8px; cursor: pointer; font-size: 13px; }}
.tab-btn.active {{ background: #e94560; color: #fff; border-color: #e94560; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Transcript */
.transcript-box {{ max-height: 400px; overflow-y: auto; font-size: 14px; line-height: 1.8; color: #ccc; }}
.transcript-box::-webkit-scrollbar {{ width: 6px; }}
.transcript-box::-webkit-scrollbar-thumb {{ background: #444; border-radius: 3px; }}

/* Workflow Bar */
.workflow-bar {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
.workflow-step {{ background: #2a2a4a; border-radius: 8px; padding: 8px 14px; font-size: 12px; color: #888; display: flex; align-items: center; gap: 6px; }}
.workflow-step.active {{ background: #7c9ff533; color: #7c9ff5; border: 1px solid #7c9ff5; }}
.workflow-step.done {{ background: #4ecdc433; color: #4ecdc4; border: 1px solid #4ecdc4; }}
.workflow-step .step-icon {{ font-size: 14px; }}
.workflow-step .step-label {{ font-weight: 500; }}
.seg {{ padding: 4px 8px; border-radius: 4px; cursor: pointer; transition: background 0.2s; display: flex; gap: 12px; }}
.seg:hover {{ background: #2a2a4a; }}
.seg.active {{ background: #e9456033; border-left: 3px solid #e94560; }}
.seg-time {{ color: #7c9ff5; font-size: 12px; min-width: 50px; cursor: pointer; flex-shrink: 0; padding-top: 2px; }}
.seg-time:hover {{ color: #e94560; text-decoration: underline; }}
.seg-text {{ flex: 1; }}

/* Script Analysis in modal */
.analysis-box {{ font-size: 14px; line-height: 1.8; color: #ccc; }}
.analysis-box .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2a4a; }}
.analysis-box .metric-label {{ color: #888; }}
.analysis-box .metric-value {{ color: #fff; font-weight: 600; }}
.analysis-box .metric-value.good {{ color: #4ecdc4; }}
.analysis-box .metric-value.warn {{ color: #ffd700; }}
.analysis-box .metric-value.bad {{ color: #e94560; }}
.analysis-box .hook-box {{ background: #1a2a1a; border-left: 3px solid #4ecdc4; padding: 12px 16px; margin: 12px 0; border-radius: 4px; font-size: 13px; }}
.analysis-box h4 {{ color: #7c9ff5; margin: 16px 0 8px 0; font-size: 14px; }}

/* Responsive */
@media (max-width: 768px) {{
    .kpi-row {{ grid-template-columns: repeat(2, 1fr); padding: 16px; }}
    .charts-grid {{ grid-template-columns: 1fr; }}
    .video-grid {{ grid-template-columns: 1fr; }}
    .section {{ padding: 0 16px; }}
}}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
    <h1>Lau博士的云组会</h1>
    <div class="subtitle">抖音号 36216723020 | AI论文精读 & 硬核科普</div>
    <div class="bio">一名做硬核科普的人工智能博士</div>
</div>

<!-- KPI Row -->
<div class="kpi-row">
    <div class="kpi-card">
        <div class="kpi-value">7.7万</div>
        <div class="kpi-label">粉丝</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{n}</div>
        <div class="kpi-label">视频数</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value blue">{avg_likes:,}</div>
        <div class="kpi-label">平均点赞</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value green">{save_rate:.0f}%</div>
        <div class="kpi-label">收藏/赞比 (干货度)</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value gold">{share_rate:.0f}%</div>
        <div class="kpi-label">分享/赞比 (传播力)</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{engagement:.1f}%</div>
        <div class="kpi-label">互动率</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value blue">{total_duration/60:.0f}分</div>
        <div class="kpi-label">总时长</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value green">{total_duration/n/60:.1f}分</div>
        <div class="kpi-label">平均时长</div>
    </div>
</div>

<!-- Key Insights -->
<div class="insight-box">
    <div class="insight">
        <h3>核心发现: 为什么火?</h3>
        <p>
            收藏/赞比高达 <span class="good">{save_rate:.0f}%</span>（行业均值 10-15%），说明内容具有极强的<span class="good">"存档价值"</span>。
            分享率 <span class="good">{share_rate:.0f}%</span> 也远超平均，论文解读天然适合"转给同事/同学"。
            <br><br>
            <span class="highlight">爆款公式</span>: [知名模型/公司] + [颠覆性结论] + [情绪标题] = 万赞级传播。
            最火两期都是 Kimi/FARS 相关，均超 <span class="highlight">1.4万赞</span>。
            <br><br>
            <span class="highlight">哑弹特征</span>: 软广内容（豆包仅 57 赞）和小众产品评测严重拉低，粉丝只为硬核 AI 内容买单。
        </p>
    </div>
    <div class="insight">
        <h3>标题策略拆解</h3>
        <p>
            <span class="good">高效公式</span>: "颠覆XX共识！" / "史上最XX！" / "XX杀疯了！" + 具体技术名词<br>
            <span class="highlight">反差感</span>: "文言文硬控大模型" "你的ViT一直用背景在分类" — 打破认知的标题吸引点击<br>
            <span class="good">权威背书</span>: "马斯克叹服" "CVPR26" "ICLR" — 顶会/名人增加可信度<br>
            <span class="highlight">失败案例</span>: "你真的会用豆包吗？" — 没有反差感，像广告，仅 57 赞
        </p>
    </div>
</div>

<!-- Script Analysis Section -->
<div class="section">
    <h2>脚本深度分析 (Whisper AI 转写)</h2>
    <div class="insight">
        <h3>语速 vs 表现</h3>
        <p>
            平均语速 <span class="good">~305 字/分钟</span>，属于中文短视频的标准节奏。
            爆款视频语速集中在 <span class="good">300-310 字/分</span>，不快不慢刚好能消化技术内容。
            过快(>320)的只有广告内容(豆包)，说明<span class="highlight">高信息密度内容需要留给观众思考时间</span>。
        </p>
    </div>
    <div class="insight">
        <h3>开场钩子分析 (前30秒定生死)</h3>
        <p>
            <span class="highlight">爆款开场公式</span>:<br>
            1. <span class="good">"恐惧/焦虑"钩子</span>: "搞AI的同学 天塌了" (FARS ❤14K) — 制造紧迫感<br>
            2. <span class="good">"认知颠覆"钩子</span>: "你知道XX是哪篇吗？没错就是..." (AttnRes ❤14K) — 先给答案再展开<br>
            3. <span class="good">"数据冲击"钩子</span>: "我们分析了25万篇论文" (AI十年 ❤7.2K) — 用数字建立权威<br>
            4. <span class="good">"反直觉"钩子</span>: "你训了几个月的ViT 其实是个背景识别器" (LaSt ❤6.5K)<br><br>
            <span class="highlight">哑弹开场</span>: "你真的会用豆包吗？"(❤57) — 没有信息差，没有情绪，像广告
        </p>
    </div>
    <div class="insight">
        <h3>关键词密度 vs 爆款概率</h3>
        <p>
            爆款视频关键词密度集中在 <span class="good">2.4%-3.0%</span>。
            密度过高(>4%)反而不利——MUDDFormer(4.2%)只有1141赞，技术太密对普通观众不友好。
            密度过低(<1%)则缺乏专业感——豆包(0.9%)和Pixverse(0.9%)表现最差。
            <br><br><span class="highlight">结论: 每100字放2-3个专业关键词是甜蜜点</span>。
        </p>
    </div>
</div>

<!-- Charts -->
<div class="charts-grid">
    <div class="chart-box">
        <h3>月度趋势</h3>
        <canvas id="monthlyChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>时长 vs 点赞 (甜蜜点分析)</h3>
        <canvas id="durationChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>TOP 5 视频对比</h3>
        <canvas id="top5Chart"></canvas>
    </div>
    <div class="chart-box">
        <h3>内容分类表现</h3>
        <canvas id="categoryChart"></canvas>
    </div>
</div>

<!-- Strategy -->
<div class="section">
    <h2>策略建议</h2>
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px;">
        <div class="strategy">
            <h3>Do - 可以学习的</h3>
            <ul>
                <li><span class="do">+</span> 紧跟 AI 大新闻，第一时间出论文解读（时效性 = 流量）</li>
                <li><span class="do">+</span> 标题公式: 震惊词 + 权威背书 + 核心话题（"颠覆10年共识！马斯克叹服！"）</li>
                <li><span class="do">+</span> 控制在 5-8 分钟，信息密度高但不过长</li>
                <li><span class="do">+</span> 结尾引导收藏（"建议收藏慢慢看"），利用高干货属性</li>
                <li><span class="do">+</span> 每周 1 条，质量优先于数量</li>
                <li><span class="do">+</span> 定位清晰: 学术 <-> 大众的桥梁，深度但不晦涩</li>
            </ul>
        </div>
        <div class="strategy">
            <h3>Don't - 需要避免的</h3>
            <ul>
                <li><span class="dont">-</span> 软广拉低数据严重（豆包 57 赞 vs 平均 4270 赞，差 75x）</li>
                <li><span class="dont">-</span> 小众/非核心 AI 内容（TicNote 315 赞，Pixverse 124 赞）</li>
                <li><span class="dont">-</span> 超过 10 分钟的视频完播率可能下降</li>
                <li><span class="dont">-</span> 标题没有"信息差"或"反差感"（"你真的会用豆包吗？" 无吸引力）</li>
                <li><span class="dont">-</span> 偏离核心受众的内容会被粉丝用脚投票</li>
            </ul>
        </div>
    </div>
</div>

<!-- Video List -->
<div class="section">
    <h2>全部视频 ({n} 个)</h2>
    <div class="controls">
        <button class="active" onclick="sortBy('date')">按时间</button>
        <button onclick="sortBy('likes')">按点赞</button>
        <button onclick="sortBy('saves')">按收藏率</button>
        <button onclick="sortBy('shares')">按分享率</button>
        <button onclick="sortBy('duration')">按时长</button>
    </div>
    <div class="video-grid" id="videoGrid">
        {video_cards}
    </div>
</div>

<!-- Video Modal -->
<div class="modal" id="videoModal">
    <div class="modal-close" onclick="closeModal()">&times;</div>
    <div class="modal-content">
        <video class="modal-video" id="modalVideo" controls autoplay playsinline></video>
        <div class="modal-info">
            <h2 id="modalTitle"></h2>
            <div class="modal-stats" id="modalStats"></div>
            <div class="workflow-bar" id="workflowBar"></div>
            <div class="modal-tabs">
                <button class="tab-btn active" onclick="switchTab('desc')">简介</button>
                <button class="tab-btn" onclick="switchTab('transcript')">完整脚本</button>
                <button class="tab-btn" onclick="switchTab('analysis')">脚本分析</button>
            </div>
            <div id="tabDesc" class="tab-content active">
                <p id="modalDesc" style="color:#aaa; font-size:14px; line-height:1.6;"></p>
            </div>
            <div id="tabTranscript" class="tab-content" style="display:none;">
                <div id="transcriptContent" class="transcript-box"></div>
            </div>
            <div id="tabAnalysis" class="tab-content" style="display:none;">
                <div id="analysisContent" class="analysis-box"></div>
            </div>
        </div>
    </div>
</div>

<div style="text-align:center; padding: 40px; color:#555; font-size: 12px;">
    Built with Playwright + curl_cffi + ffmpeg | Data crawled from iesdouyin.com
</div>

<script>
// Video data for modal
const videoData = {json.dumps({v['id']: v for v in VIDEOS}, ensure_ascii=False)};
const videoFiles = {json.dumps({vid: True for vid in VID_FILES}, ensure_ascii=False)};
const transcripts = {json.dumps(TRANSCRIPTS, ensure_ascii=False)};
const scriptAnalysis = {json.dumps(SCRIPT_ANALYSIS, ensure_ascii=False)};

function showVideo(id) {{
    const v = videoData[id];
    if (!v) return;
    const modal = document.getElementById('videoModal');
    const video = document.getElementById('modalVideo');

    // Reset video
    video.pause();
    video.src = '';

    const hasFile = !!videoFiles[id];
    const hasTranscript = !!transcripts[id];
    const hasAnalysis = !!scriptAnalysis[id];

    if (hasFile) {{
        video.src = '/video/' + id;
        video.style.display = 'block';
        // 自动播放
        video.onloadedmetadata = () => video.play().catch(() => {{}});
    }} else {{
        video.style.display = 'none';
    }}

    document.getElementById('modalTitle').textContent = v.desc.split('\\n')[0];

    // Workflow status bar
    const steps = [
        {{ key: 'download', label: '下载视频', icon: hasFile ? '✅' : '⬜', done: hasFile }},
        {{ key: 'transcript', label: '语音转写', icon: hasFile && hasTranscript ? '✅' : (hasFile ? '⬜' : '⬜'), done: hasFile && hasTranscript, disabled: !hasFile }},
        {{ key: 'analysis', label: '脚本分析', icon: hasFile && hasTranscript && hasAnalysis ? '✅' : (hasFile && hasTranscript ? '⬜' : '⬜'), done: hasFile && hasTranscript && hasAnalysis, disabled: !hasFile || !hasTranscript }},
    ];
    document.getElementById('workflowBar').innerHTML = steps.map(s => {{
        let cls = s.done ? 'done' : (!s.disabled ? 'active' : '');
        let icon = s.icon;
        return `<div class="workflow-step ${{cls}}"><span class="step-icon">${{icon}}</span><span class="step-label">${{s.label}}</span></div>`;
    }}).join('');

    // Stats
    const saveRate = (v.collect_count / Math.max(v.digg_count, 1) * 100).toFixed(0);
    const shareRate = (v.share_count / Math.max(v.digg_count, 1) * 100).toFixed(0);
    const dur = v.duration_sec ? Math.floor(v.duration_sec/60) + ':' + String(Math.floor(v.duration_sec%60)).padStart(2,'0') : '?';
    const date = v.create_time ? new Date(v.create_time * 1000).toLocaleDateString('zh-CN') : '?';

    document.getElementById('modalStats').innerHTML = `
        <div class="modal-stat"><div class="val" style="color:#e94560">${{v.digg_count.toLocaleString()}}</div><div class="lbl">点赞</div></div>
        <div class="modal-stat"><div class="val" style="color:#7c9ff5">${{v.comment_count.toLocaleString()}}</div><div class="lbl">评论</div></div>
        <div class="modal-stat"><div class="val" style="color:#ffd700">${{v.share_count.toLocaleString()}}</div><div class="lbl">分享</div></div>
        <div class="modal-stat"><div class="val" style="color:#4ecdc4">${{v.collect_count.toLocaleString()}}</div><div class="lbl">收藏</div></div>
        <div class="modal-stat"><div class="val">${{saveRate}}%</div><div class="lbl">收藏率</div></div>
        <div class="modal-stat"><div class="val">${{shareRate}}%</div><div class="lbl">分享率</div></div>
        <div class="modal-stat"><div class="val">${{dur}}</div><div class="lbl">时长</div></div>
        <div class="modal-stat"><div class="val">${{date}}</div><div class="lbl">发布</div></div>
    `;

    // Description tab
    document.getElementById('modalDesc').textContent = v.desc;

    // Transcript tab
    const transcriptBox = document.getElementById('transcriptContent');
    const t = transcripts[id];
    if (t && t.segments) {{
        transcriptBox.innerHTML = t.segments.map((s, i) => {{
            const mm = Math.floor(s.start / 60);
            const ss = Math.floor(s.start % 60);
            const timeStr = mm + ':' + String(ss).padStart(2, '0');
            return `<div class="seg" data-time="${{s.start}}" id="seg-${{i}}"><span class="seg-time" onclick="seekTo(${{s.start}})">${{timeStr}}</span><span class="seg-text">${{s.text}}</span></div>`;
        }}).join('');
    }} else if (!hasFile) {{
        transcriptBox.innerHTML = '<p style="color:#666; padding:20px; text-align:center;">⬆ 请先下载视频</p>';
    }} else {{
        transcriptBox.innerHTML = '<p style="color:#888; padding:20px; text-align:center;">待转写 ⬜<br><br><code style="background:#2a2a4a; padding:6px 12px; border-radius:4px; font-size:12px; color:#4ecdc4;">python transcribe_videos.py --input videos/lau_all/ --output web_demo/all_transcripts.json</code><br><br><span style="font-size:11px; color:#666;">运行上述命令后刷新页面</span></p>';
    }}

    // Analysis tab
    const analysisBox = document.getElementById('analysisContent');
    const a = scriptAnalysis[id];
    if (a) {{
        const cpmClass = a.chars_per_min >= 295 && a.chars_per_min <= 315 ? 'good' : (a.chars_per_min > 320 ? 'bad' : 'warn');
        const kwTotal = a.ai_keywords + a.emotion_keywords + a.tech_keywords;
        const kwDensity = (kwTotal / a.char_count * 100).toFixed(1);
        const kwClass = kwDensity >= 2.0 && kwDensity <= 3.5 ? 'good' : (kwDensity < 1.5 ? 'bad' : 'warn');
        const emotionClass = a.emotion_keywords >= 5 ? 'good' : (a.emotion_keywords < 2 ? 'bad' : 'warn');

        analysisBox.innerHTML = `
            <div class="metric"><span class="metric-label">总字数</span><span class="metric-value">${{a.char_count.toLocaleString()}} 字</span></div>
            <div class="metric"><span class="metric-label">语速</span><span class="metric-value ${{cpmClass}}">${{a.chars_per_min}} 字/分 ${{cpmClass === 'good' ? '(最佳区间)' : cpmClass === 'bad' ? '(偏快)' : '(略偏)'}}</span></div>
            <div class="metric"><span class="metric-label">段落数</span><span class="metric-value">${{a.segment_count}} 段 (avg ${{a.avg_seg_chars}} 字/段)</span></div>
            <div class="metric"><span class="metric-label">AI 关键词</span><span class="metric-value">${{a.ai_keywords}} 次</span></div>
            <div class="metric"><span class="metric-label">情绪词</span><span class="metric-value ${{emotionClass}}">${{a.emotion_keywords}} 次 ${{emotionClass === 'good' ? '(情绪到位)' : '(偏少)'}}</span></div>
            <div class="metric"><span class="metric-label">技术词</span><span class="metric-value">${{a.tech_keywords}} 次</span></div>
            <div class="metric"><span class="metric-label">关键词密度</span><span class="metric-value ${{kwClass}}">${{kwDensity}}% ${{kwClass === 'good' ? '(甜蜜点)' : kwClass === 'bad' ? '(偏低)' : '(偏高)'}}</span></div>
            <h4>开场钩子 (前30秒)</h4>
            <div class="hook-box">${{a.hook_text || '无数据'}}</div>
            <h4>结尾收束 (最后30秒)</h4>
            <div class="hook-box">${{a.close_text || '无数据'}}</div>
        `;
    }} else if (!hasTranscript) {{
        analysisBox.innerHTML = '<p style="color:#666; padding:20px; text-align:center;">⬆ 请先完成语音转写</p>';
    }} else {{
        analysisBox.innerHTML = '<p style="color:#888; padding:20px; text-align:center;">待分析 ⬜<br><br><code style="background:#2a2a4a; padding:6px 12px; border-radius:4px; font-size:12px; color:#4ecdc4;">python analyze_scripts.py</code><br><br><span style="font-size:11px; color:#666;">运行上述命令后刷新页面</span></p>';
    }}

    // Reset to first tab
    switchTab('desc');
    modal.classList.add('show');

    // Sync transcript highlight with video playback
    if (hasFile) {{
        video.ontimeupdate = () => {{
            const ct = video.currentTime;
            const segs = document.querySelectorAll('.seg');
            segs.forEach((s, i) => {{
                const t = parseFloat(s.dataset.time);
                const next = segs[i+1] ? parseFloat(segs[i+1].dataset.time) : Infinity;
                if (ct >= t && ct < next) {{
                    if (!s.classList.contains('active')) {{
                        segs.forEach(x => x.classList.remove('active'));
                        s.classList.add('active');
                        const tabT = document.getElementById('tabTranscript');
                        if (tabT.style.display !== 'none') {{
                            s.scrollIntoView({{ block: 'center', behavior: 'smooth' }});
                        }}
                    }}
                }}
            }});
        }};
    }}
}}

function seekTo(time) {{
    const video = document.getElementById('modalVideo');
    if (video.src) {{
        video.currentTime = time;
        video.play();
    }}
}}

function switchTab(tab) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => {{ t.style.display = 'none'; t.classList.remove('active'); }});
    const tabEl = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (tabEl) {{ tabEl.style.display = 'block'; tabEl.classList.add('active'); }}
    // Activate matching button
    document.querySelectorAll('.tab-btn').forEach(b => {{
        if (b.textContent.trim().startsWith(tab === 'desc' ? '简介' : tab === 'transcript' ? '完整脚本' : '脚本分析')) {{
            b.classList.add('active');
        }}
    }});
}}

function closeModal() {{
    const modal = document.getElementById('videoModal');
    const video = document.getElementById('modalVideo');
    video.pause();
    video.src = '';
    modal.classList.remove('show');
}}

document.getElementById('videoModal').addEventListener('click', function(e) {{
    if (e.target === this) closeModal();
}});

// Sorting
function sortBy(key) {{
    const grid = document.getElementById('videoGrid');
    const cards = [...grid.children];
    cards.sort((a, b) => {{
        if (key === 'date') return b.dataset.date - a.dataset.date;
        if (key === 'likes') return b.dataset.likes - a.dataset.likes;
        if (key === 'duration') return b.dataset.duration - a.dataset.duration;
        if (key === 'saves') {{
            const va = videoData[a.querySelector('.thumb')?.src?.match(/\\d{{18,}}/)?.[0]] || {{}};
            const vb = videoData[b.querySelector('.thumb')?.src?.match(/\\d{{18,}}/)?.[0]] || {{}};
            return (vb.collect_count/(vb.digg_count||1)) - (va.collect_count/(va.digg_count||1));
        }}
        if (key === 'shares') {{
            const va = videoData[a.querySelector('.thumb')?.src?.match(/\\d{{18,}}/)?.[0]] || {{}};
            const vb = videoData[b.querySelector('.thumb')?.src?.match(/\\d{{18,}}/)?.[0]] || {{}};
            return (vb.share_count/(vb.digg_count||1)) - (va.collect_count/(va.digg_count||1));
        }}
        return 0;
    }});
    cards.forEach(c => grid.appendChild(c));
    document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
    // Find and activate the clicked button by matching sort key text
    const keyLabels = {{ date: '按时间', likes: '按点赞', saves: '按收藏率', shares: '按分享率', duration: '按时长' }};
    document.querySelectorAll('.controls button').forEach(b => {{
        if (b.textContent.trim() === keyLabels[key]) b.classList.add('active');
    }});
}}

// Charts
Chart.defaults.color = '#aaa';
Chart.defaults.borderColor = '#2a2a4a';

// Monthly Trend
new Chart(document.getElementById('monthlyChart'), {{
    type: 'bar',
    data: {{
        labels: {monthly_labels},
        datasets: [
            {{ label: '总点赞', data: {monthly_likes}, backgroundColor: 'rgba(233,69,96,0.7)', yAxisID: 'y' }},
            {{ label: '平均点赞', data: {monthly_avg}, type: 'line', borderColor: '#4ecdc4', yAxisID: 'y1', tension: 0.3 }},
        ]
    }},
    options: {{
        responsive: true,
        scales: {{
            y: {{ position: 'left', title: {{ display: true, text: '总点赞' }} }},
            y1: {{ position: 'right', grid: {{ display: false }}, title: {{ display: true, text: '平均点赞' }} }}
        }}
    }}
}});

// Duration vs Likes scatter
new Chart(document.getElementById('durationChart'), {{
    type: 'scatter',
    data: {{
        datasets: [{{
            label: '视频',
            data: {dur_json},
            backgroundColor: 'rgba(124,159,245,0.8)',
            pointRadius: 8,
            pointHoverRadius: 12,
        }}]
    }},
    options: {{
        responsive: true,
        scales: {{
            x: {{ title: {{ display: true, text: '时长 (分钟)' }} }},
            y: {{ title: {{ display: true, text: '点赞数' }} }}
        }},
        plugins: {{
            tooltip: {{
                callbacks: {{
                    label: (ctx) => ctx.raw.title + ': ' + ctx.raw.y.toLocaleString() + ' 赞'
                }}
            }}
        }}
    }}
}});

// Top 5
new Chart(document.getElementById('top5Chart'), {{
    type: 'bar',
    data: {{
        labels: {top5_labels},
        datasets: [
            {{ label: '点赞', data: {top5_likes}, backgroundColor: 'rgba(233,69,96,0.7)' }},
            {{ label: '收藏', data: {top5_collects}, backgroundColor: 'rgba(78,205,196,0.7)' }},
            {{ label: '分享', data: {top5_shares}, backgroundColor: 'rgba(255,215,0,0.7)' }},
        ]
    }},
    options: {{
        responsive: true,
        indexAxis: 'y',
    }}
}});

// Category
new Chart(document.getElementById('categoryChart'), {{
    type: 'doughnut',
    data: {{
        labels: {cat_labels},
        datasets: [{{
            data: {cat_avg_likes},
            backgroundColor: ['#e94560', '#ffd700', '#4ecdc4', '#7c9ff5', '#888'],
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            title: {{ display: true, text: '各分类平均点赞' }}
        }}
    }}
}});
</script>
</body>
</html>"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            html = build_index_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif path.startswith("/thumbnails/"):
            fname = path.split("/")[-1]
            fpath = BASE / "thumbnails" / fname
            if fpath.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(fpath.read_bytes())
            else:
                self.send_error(404)

        elif path.startswith("/video/"):
            vid = path.split("/")[-1]
            if vid in VID_FILES:
                fpath = VID_FILES[vid]
                if fpath.is_symlink():
                    fpath = fpath.resolve()
                size = fpath.stat().st_size

                # Support range requests for video seeking
                range_header = self.headers.get("Range")
                if range_header:
                    start, end = 0, size - 1
                    m = re.match(r"bytes=(\d+)-(\d*)", range_header)
                    if m:
                        start = int(m.group(1))
                        if m.group(2):
                            end = int(m.group(2))
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(fpath, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with open(fpath, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
            else:
                self.send_error(404)

        elif path == "/data.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(DATA, ensure_ascii=False).encode("utf-8"))

        elif path.startswith("/transcript/"):
            vid = path.split("/")[-1]
            if vid in TRANSCRIPTS:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(TRANSCRIPTS[vid], ensure_ascii=False).encode("utf-8"))
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress logs


if __name__ == "__main__":
    print(f"Starting server at http://localhost:{PORT}")
    thumb_dir = BASE / "thumbnails"
    thumb_count = len(list(thumb_dir.glob("*.jpg"))) if thumb_dir.exists() else 0
    print(f"Videos: {len(VID_FILES)} files, Thumbnails: {thumb_count} files")
    print(f"Press Ctrl+C to stop")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
