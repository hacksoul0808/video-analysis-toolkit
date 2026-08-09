#!/usr/bin/env python3
"""
Video Script Analyzer - API Server

Serves analyzer.html SPA + API endpoints for video analysis pipeline.
Run: python server.py
Open: http://localhost:8840
"""

import json
import os
import re
import sys
import time
import shutil
import subprocess
import threading
import traceback
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from socketserver import ThreadingMixIn

# ── Load .env ──────────────────────────────────────
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val

_load_env()

# ── Paths ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LIBRARY_DIR = BASE_DIR / "library"
LIBRARY_FILE = LIBRARY_DIR / "library.json"
TAGS_FILE = LIBRARY_DIR / "tags.json"
VIDEOS_DIR = LIBRARY_DIR / "videos"
PORT = int(os.environ.get("PORT", 8840))

# Ensure directories
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# ── Library CRUD ───────────────────────────────────

def load_library():
    if LIBRARY_FILE.exists():
        with open(LIBRARY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"videos": [], "updated_at": ""}

def save_library(data):
    data["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_tags():
    if TAGS_FILE.exists():
        with open(TAGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tags(tags_data):
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)

# ── Progress Store ─────────────────────────────────
progress_store = {}  # {video_id: {"percent": 45, "status": "downloading|done|error"}}

# ── Video Download ─────────────────────────────────

def download_video(url, output_dir, video_id):
    """Call vdl.py to download video, return metadata dict. Reports progress in real-time."""
    print(f"[server {time.strftime('%H:%M:%S')}] download_video 开始: {video_id} ← {url[:80]}")
    t0 = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    before = set(f.name for f in output_dir.glob("*.mp4") if f.is_file())

    vdl_path = BASE_DIR / "vdl.py"
    progress_store[video_id] = {"percent": 0, "status": "downloading"}

    process = subprocess.Popen(
        [sys.executable, str(vdl_path), url, "-o", str(output_dir)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace", bufsize=1, cwd=str(BASE_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )

    stdout_lines = []

    def reader():
        for line in iter(process.stdout.readline, ''):
            line_stripped = line.strip()
            stdout_lines.append(line_stripped)
            # 输出到 Console, 方便调试
            if line_stripped:
                print(f"  [vdl] {line_stripped}", flush=True)
            m = re.search(r'PROGRESS:(\d+)', line_stripped)
            if m:
                pct = int(m.group(1))
                progress_store[video_id] = {"percent": pct, "status": "downloading"}
            # Also parse yt-dlp progress: [download] 45.2% of ...
            m2 = re.search(r'\[download\]\s+(\d+\.?\d*)%', line_stripped)
            if m2:
                pct = int(float(m2.group(1)))
                progress_store[video_id] = {"percent": pct, "status": "downloading"}

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    process.wait(timeout=600)
    t.join(timeout=3)

    elapsed = time.time() - t0
    stdout_full = "\n".join(stdout_lines)

    if process.returncode != 0:
        print(f"[server {time.strftime('%H:%M:%S')}] download_video 失败, rc={process.returncode}, 耗时 {elapsed:.1f}s")
        progress_store[video_id] = {"percent": 100, "status": "error", "error": stdout_full[-500:]}
        err_lines = stdout_lines[-5:] if stdout_lines else ["Unknown error"]
        raise RuntimeError("下载失败:\n" + "\n".join(err_lines))

    print(f"[server {time.strftime('%H:%M:%S')}] download_video 完成, 耗时 {elapsed:.1f}s")
    progress_store[video_id] = {"percent": 100, "status": "done"}

    # Find the new mp4 file
    after = set(f.name for f in output_dir.glob("*.mp4") if f.is_file())
    new_files = after - before

    if not new_files:
        err_lines = stdout_lines[-5:] if stdout_lines else ["Unknown error"]
        raise RuntimeError("下载失败: 未找到下载文件\n" + "\n".join(err_lines))

    filename = sorted(new_files)[-1]
    filepath = output_dir / filename
    size_mb = round(filepath.stat().st_size / 1024 / 1024, 1)

    # Try to extract title from stdout
    title = filename.rsplit(".", 1)[0][:100]
    m = re.search(r"标题:\s*(.+?)(?:\n|$)", stdout_full)
    if m:
        title = m.group(1).strip()[:120]
    else:
        m = re.search(r"\[download\]\s+Destination:\s*(.+\.mp4)", stdout_full)
        if m:
            title = Path(m.group(1)).stem[:100]

    vid_match = re.search(r"(\d{15,})", filename)
    actual_video_id = vid_match.group(1) if vid_match else filename.rsplit(".", 1)[0]

    platform = "unknown"
    plat_patterns = {
        "douyin": r"(douyin\.com|iesdouyin\.com)",
        "youtube": r"(youtube\.com|youtu\.be)",
        "bilibili": r"bilibili\.com",
        "tiktok": r"tiktok\.com",
    }
    for plat, pat in plat_patterns.items():
        if re.search(pat, url, re.I):
            platform = plat
            break

    return {
        "video_id": actual_video_id,
        "title": title,
        "platform": platform,
        "url": url,
        "filename": filename,
        "file_size_mb": size_mb,
    }


# ── Transcription ──────────────────────────────────

def transcribe_video_file(video_path, output_json_path, progress_callback=None):
    """Transcribe a single video using faster-whisper.
    Args:
        progress_callback: Optional callable(int percent) for real-time progress. 0-100."""
    print(f"[server {time.strftime('%H:%M:%S')}] transcribe_video_file 开始: {video_path}")
    t0 = time.time()

    # 检查 CUDA 可用性
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        print(f"[server {time.strftime('%H:%M:%S')}] CUDA available: {cuda_ok}")
    except Exception as e:
        print(f"[server {time.strftime('%H:%M:%S')}] torch check failed: {e}")
        cuda_ok = False

    # 设置 HuggingFace 镜像（国内加速）
    hf_endpoint = os.environ.get("HF_ENDPOINT", "")
    if not hf_endpoint:
        # 自动尝试国内镜像
        hf_mirror = "https://hf-mirror.com"
        os.environ["HF_ENDPOINT"] = hf_mirror
        print(f"[server {time.strftime('%H:%M:%S')}] 设置 HF_ENDPOINT={hf_mirror}")

    device = "cuda" if cuda_ok else "cpu"
    compute_type = "float16" if cuda_ok else "int8"

    print(f"[server {time.strftime('%H:%M:%S')}] 加载 faster-whisper 模型 small, device={device}, compute_type={compute_type}")
    from faster_whisper import WhisperModel

    try:
        model_path = str(Path(__file__).parent / "Model-s")
        model = WhisperModel(model_path, device=device, compute_type=compute_type)
        print(f"[server {time.strftime('%H:%M:%S')}] 模型加载完成, 耗时 {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"[server {time.strftime('%H:%M:%S')}] 模型加载失败: {e}")
        raise

    if progress_callback:
        progress_callback(5)  # model loaded

    print(f"[server {time.strftime('%H:%M:%S')}] 开始转写...")
    segments_list, info = model.transcribe(
        str(video_path),
        beam_size=5,
        language="zh",
        vad_filter=True,
    )

    segments = []
    total_dur = info.duration
    for seg in segments_list:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        if progress_callback and total_dur > 0:
            pct = min(int(seg.end / total_dur * 90) + 5, 94)
            progress_callback(pct)

    if progress_callback:
        progress_callback(100)

    char_count = sum(len(s["text"]) for s in segments)
    result = {
        "video_id": Path(output_json_path).parent.name,
        "language": info.language,
        "duration": round(info.duration, 1),
        "segments": segments,
        "char_count": char_count,
        "segment_count": len(segments),
    }

    output_json_path = Path(output_json_path)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"[server {time.strftime('%H:%M:%S')}] 转写完成, 耗时 {elapsed:.1f}s, {len(segments)} segments, {char_count} chars")
    return result


# ── Script Analysis ────────────────────────────────

AI_KEYWORDS = [
    "transformer", "attention", "模型", "训练", "推理", "参数",
    "token", "embedding", "大模型", "神经网络", "深度学习",
    "卷积", "残差", "归一化", "softmax", "向量", "矩阵",
    "encoder", "decoder", "微调", "预训练", "prompt", "inference",
]

EMOTION_KEYWORDS = [
    "震惊", "颠覆", "疯", "杀疯", "爆", "炸", "恐怖",
    "太强了", "牛", "厉害", "可怕", "惊人", "离谱", "逆天",
    "绝了", "炸裂", "突破", "革命", "划时代", "史上最",
]

TECH_KEYWORDS = [
    "CVPR", "ICLR", "NeurIPS", "ICML", "AAAI",
    "开源", "论文", "实验", "数据集", "benchmark",
    "GPU", "CUDA", "API", "GitHub", "代码",
    "准确率", "精度", "性能", "效率", "速度",
]


def analyze_transcript(transcript_data):
    """Analyze transcript for speech rate, keywords, hooks."""
    segments = transcript_data.get("segments", [])
    if not segments:
        return None

    full_text = " ".join(s["text"] for s in segments)
    char_count = len(full_text.replace(" ", ""))
    duration = transcript_data.get("duration", 0)

    chars_per_min = round(char_count / (duration / 60)) if duration > 0 else 0
    text_lower = full_text.lower()

    ai_count = sum(1 for kw in AI_KEYWORDS if kw.lower() in text_lower)
    emotion_count = sum(1 for kw in EMOTION_KEYWORDS if kw in full_text)
    tech_count = sum(1 for kw in TECH_KEYWORDS if kw in full_text or kw.lower() in text_lower)

    hook_segments = [s for s in segments if s["start"] < 30]
    hook_text = " ".join(s["text"] for s in hook_segments)

    close_segments = [s for s in segments if s["start"] > duration - 30] if duration > 30 else []
    close_text = " ".join(s["text"] for s in close_segments)

    keyword_density = round((ai_count + emotion_count + tech_count) / char_count * 100, 2) if char_count > 0 else 0

    return {
        "char_count": char_count,
        "duration": round(duration, 1),
        "chars_per_min": chars_per_min,
        "segment_count": len(segments),
        "avg_seg_chars": round(char_count / len(segments)) if segments else 0,
        "ai_keywords": ai_count,
        "emotion_keywords": emotion_count,
        "tech_keywords": tech_count,
        "keyword_density": keyword_density,
        "hook_text": hook_text[:300],
        "close_text": close_text[:300],
    }


# ── DeepSeek AI Analysis ───────────────────────────

SYSTEM_PROMPT = """你是一位顶级短视频文案分析师，曾服务于头部 MCN 机构。你的任务是深度分析视频转写文案，输出可直接落地的爆款方法论。

分析时必须严格遵循以下结构输出 Markdown：

## 🎯 爆款公式拆解
- 开场钩子类型（恐惧/认知颠覆/数据冲击/反直觉，四选一）
- 情绪节奏曲线（标注时间节点）
- 信息密度分布（高/中/低 + 时间区间）
- 标题公式提取（给出可复用的模板）
- 引导转化策略

## 📋 可复制模板
### 标题模板
（含 {占位符} 的模板）
### 结构模板
（Hook-Why-How-CTA 或自定义分步结构）

## 📊 同类对比分析
仅基于提供的参考数据对比（收藏率/分享率/语速/情绪词），给出差异化分析

## 🔧 改进建议
3 条具体可执行的优化建议（标题/节奏/话术）

## 🏷️ 自动标签
从预设标签库中选择 3-6 个最匹配的标签，格式: `#标签1 #标签2`

标签库: 论文精读, 行业热点, 产品测评, 商务合作, 科普教程, 教程向, 收藏向, 传播向, AI, 深度学习, 颠覆性结论, 数据驱动, 认知升级, 实用技巧, 3分钟以内, 5-8分钟, 10分钟以上, 爆款, 优质, 普通, 幽默, 严肃, 温情, 焦虑, 励志"""


def call_deepseek(video_info, transcript_data, script_stats):
    """Call DeepSeek API for viral script analysis."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        return {
            "error": "DeepSeek API Key 未配置。请设置环境变量 DEEPSEEK_API_KEY",
            "report": "",
            "tags": [],
            "viral_score": 0
        }

    try:
        from openai import OpenAI
    except ImportError:
        return {
            "error": "请安装 openai 库: pip install openai",
            "report": "",
            "tags": [],
            "viral_score": 0
        }

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Build user prompt
    segments = transcript_data.get("segments", [])
    full_text = " ".join(s["text"] for s in segments)
    hook_text = script_stats.get("hook_text", "") if script_stats else ""

    duration = transcript_data.get("duration", 0)
    char_count = script_stats.get("char_count", 0) if script_stats else 0
    cpm = script_stats.get("chars_per_min", 0) if script_stats else 0
    emotion = script_stats.get("emotion_keywords", 0) if script_stats else 0
    kd = script_stats.get("keyword_density", 0) if script_stats else 0

    user_prompt = f"""分析以下短视频文案，参考数据：
- 标题: {video_info.get('title', '未知')}
- 时长: {duration}秒
- 总字数: {char_count}
- 语速: {cpm}字/分钟
- 情绪词数量: {emotion}个
- 关键词密度: {kd}%
- 平台: {video_info.get('platform', '未知')}

开场(前30秒):
{hook_text}

完整转写文本:
{full_text}"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        report = response.choices[0].message.content
    except Exception as e:
        return {
            "error": f"DeepSeek API 调用失败: {str(e)}",
            "report": "",
            "tags": [],
            "viral_score": 0
        }

    # Extract tags from report
    tags = []
    tag_match = re.findall(r'#(\S+)', report)
    if tag_match:
        tags = tag_match
    else:
        # Fallback: extract from the tags section
        m = re.search(r'##\s*🏷️.*?\n(.*?)(?:\n##|\Z)', report, re.DOTALL)
        if m:
            tags = re.findall(r'#(\S+)', m.group(1))

    # Calculate viral score
    viral_score = _calculate_viral_score(report, script_stats, video_info)

    return {
        "error": None,
        "report": report,
        "tags": tags,
        "viral_score": viral_score,
    }


def _calculate_viral_score(report, script_stats, video_info):
    """Calculate 0-100 viral score from report content and stats."""
    score = 50  # baseline

    # Hook quality (0-25)
    if "认知颠覆" in report or "反直觉" in report:
        score += 12
    if "数据冲击" in report:
        score += 10
    if "恐惧" in report:
        score += 8

    # Structure score (0-25): check for all sections
    if "Hook" in report or "开场" in report:
        score += 8
    if "Why" in report or "为什么" in report:
        score += 7
    if "CTA" in report or "引导" in report or "收藏" in report:
        score += 5
    if "## 📋 可复制模板" in report:
        score += 5

    # Emotion density (0-20)
    if script_stats:
        emo = script_stats.get("emotion_keywords", 0)
        if emo >= 7:
            score += 20
        elif emo >= 5:
            score += 15
        elif emo >= 3:
            score += 10
        else:
            score += 5

    # Engagement ratio (from video_info or defaults)
    engagement_bonus = 0
    # If we have video data with metrics, use it
    score += min(engagement_bonus, 15)

    # Template reusability (0-15)
    if "{占位符}" in report or "{标题}" in report or "模板" in report:
        score += 10
    if "## 📋" in report:
        score += 5

    return min(score, 100)


# ── Tag Management ─────────────────────────────────

def update_tags_system(video_tags):
    """Update global tags.json with new tags from a video."""
    tags_data = load_tags()
    all_tags = tags_data.get("tags", {})

    for tag in video_tags:
        if tag in all_tags:
            all_tags[tag] += 1
        else:
            all_tags[tag] = 1

    tags_data["tags"] = all_tags
    save_tags(tags_data)


def get_all_tags():
    """Get sorted list of all tags with counts."""
    tags_data = load_tags()
    tags = tags_data.get("tags", {})
    return sorted(tags.items(), key=lambda x: -x[1])


# ── Methodology Aggregation ────────────────────────

def aggregate_methodology(library_data, tag_filter=None):
    """Aggregate viral patterns across videos, optionally filtered by tag."""
    videos = library_data.get("videos", [])
    if tag_filter:
        videos = [v for v in videos if tag_filter in v.get("tags", [])]

    # Aggregate patterns from reports
    all_hooks = {}
    all_templates = []
    best_examples = []

    for v in videos:
        vid = v["id"]
        report_path = VIDEOS_DIR / vid / "deepseek_report.md"
        if not report_path.exists():
            continue

        with open(report_path, encoding="utf-8") as f:
            report = f.read()

        # Extract hook type
        hook_match = re.search(r'开场钩子类型[：:]\s*(\S+)', report)
        if hook_match:
            hook_type = hook_match.group(1)
            all_hooks[hook_type] = all_hooks.get(hook_type, 0) + 1

        # Extract title templates
        tmpl_matches = re.findall(r'[「"{]([^「"{]*?\{[^}]*?\}[^」"}]*?)[」"}]', report)
        for t in tmpl_matches[:3]:
            if len(t) > 5 and t not in all_templates:
                all_templates.append(t)

        # Best examples
        if v.get("viral_score", 0) >= 75 and len(best_examples) < 5:
            best_examples.append({
                "id": vid,
                "title": v.get("title", ""),
                "viral_score": v.get("viral_score", 0),
                "tags": v.get("tags", []),
            })

    return {
        "hook_patterns": sorted(all_hooks.items(), key=lambda x: -x[1]),
        "title_templates": all_templates[:10],
        "best_examples": best_examples,
        "total_analyzed": len(videos),
    }


# ── HTTP Handler ───────────────────────────────────

class APIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for API + SPA serving."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/":
                self._serve_html()
            elif path == "/api/library":
                self._handle_get_library(query)
            elif path == "/api/stats":
                self._handle_get_stats()
            elif path == "/api/scan-videos":
                self._handle_scan_videos()
            elif path == "/api/methodology":
                self._handle_get_methodology(query)
            elif path == "/api/tags":
                self._handle_get_tags()
            elif path == "/api/progress":
                self._handle_get_progress(query)
            elif path.startswith("/api/video-file/"):
                self._handle_video_file(path)
            elif path.startswith("/sounds/"):
                self._handle_sound(path)
            elif path.startswith("/api/video/"):
                self._handle_get_video(path, query)
            else:
                self.send_error(404, "Not found")
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Client disconnected, ignore silently
        except Exception as e:
            self._send_json_safe({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = {}
            if length > 0:
                raw = self.rfile.read(length).decode("utf-8")
                body = json.loads(raw) if raw else {}

            if path == "/api/download":
                self._handle_download(body)
            elif path == "/api/transcribe":
                self._handle_transcribe(body)
            elif path == "/api/analyze":
                self._handle_analyze(body)
            elif path == "/api/process":
                self._handle_pipeline(body)
            elif path == "/api/batch-analyze":
                self._handle_batch_analyze(body)
            elif path == "/api/save":
                self._handle_save(body)
            elif path == "/api/delete":
                self._handle_delete(body)
            elif path == "/api/tags":
                self._handle_tags(body)
            elif path == "/api/import":
                self._handle_import_video(body)
            else:
                self.send_error(404, "Not found")
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Client disconnected, ignore silently
        except Exception as e:
            self._send_json_safe({"error": str(e)}, 500)

    # ── GET handlers ────────────────────────────

    def _send_json_safe(self, data, status=500):
        """Send JSON error without crashing on dead connection."""
        try:
            self._send_json(data, status)
        except OSError:
            pass

    def _serve_html(self):
        html_path = BASE_DIR / "analyzer.html"
        if not html_path.exists():
            self._send_json({"error": "analyzer.html not found. Please create the frontend file."}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        with open(html_path, "rb") as f:
            self.wfile.write(f.read())

    def _handle_get_library(self, query):
        lib = load_library()
        videos = lib.get("videos", [])

        # Filter by tag
        tag = query.get("tag", [None])[0]
        if tag:
            videos = [v for v in videos if tag in v.get("tags", [])]

        # Full-text search (title + transcript content)
        q = query.get("q", [None])[0]
        if q:
            q_lower = q.lower()
            filtered = []
            for v in videos:
                if q_lower in (v.get("title", "") or v.get("id", "")).lower():
                    filtered.append(v)
                    continue
                # Search in transcript
                tp = VIDEOS_DIR / v.get("id", "") / "transcript.json"
                if tp.exists():
                    try:
                        with open(tp, encoding="utf-8") as f:
                            trans = json.load(f)
                        full_text = " ".join(s.get("text", "") for s in trans.get("segments", []))
                        if q_lower in full_text.lower():
                            filtered.append(v)
                    except Exception:
                        pass
            videos = filtered

        # Sort
        sort = query.get("sort", ["created_at"])[0]
        if sort == "likes":
            videos.sort(key=lambda x: x.get("metrics", {}).get("likes", 0), reverse=True)
        elif sort == "viral_score":
            videos.sort(key=lambda x: x.get("viral_score", 0), reverse=True)
        elif sort == "duration":
            videos.sort(key=lambda x: x.get("duration_sec", 0), reverse=True)
        else:
            videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        self._send_json({"videos": videos, "total": len(videos), "tags": get_all_tags()})

    def _handle_get_stats(self):
        lib = load_library()
        videos = lib.get("videos", [])

        total = len(videos)
        if total == 0:
            self._send_json({"total_videos": 0, "by_tag": {}, "avg_viral_score": 0})
            return

        avg_score = sum(v.get("viral_score", 0) for v in videos) / total

        # By tag
        by_tag = {}
        for v in videos:
            for t in v.get("tags", []):
                if t not in by_tag:
                    by_tag[t] = {"count": 0, "total_score": 0, "total_likes": 0}
                by_tag[t]["count"] += 1
                by_tag[t]["total_score"] += v.get("viral_score", 0)
                by_tag[t]["total_likes"] += v.get("metrics", {}).get("likes", 0)

        for t in by_tag:
            c = by_tag[t]["count"]
            by_tag[t]["avg_score"] = round(by_tag[t]["total_score"] / c, 1) if c else 0
            by_tag[t]["avg_likes"] = round(by_tag[t]["total_likes"] / c, 1) if c else 0

        # Score distribution
        score_dist = {"爆款(80+)": 0, "优质(60-79)": 0, "普通(40-59)": 0, "低迷(<40)": 0}
        for v in videos:
            s = v.get("viral_score", 0)
            if s >= 80:
                score_dist["爆款(80+)"] += 1
            elif s >= 60:
                score_dist["优质(60-79)"] += 1
            elif s >= 40:
                score_dist["普通(40-59)"] += 1
            else:
                score_dist["低迷(<40)"] += 1

        self._send_json({
            "total_videos": total,
            "avg_viral_score": round(avg_score, 1),
            "by_tag": by_tag,
            "score_distribution": score_dist,
        })

    def _handle_get_methodology(self, query):
        tag = query.get("tag", [None])[0]
        lib = load_library()
        result = aggregate_methodology(lib, tag)
        self._send_json(result)

    def _handle_get_tags(self):
        self._send_json({"tags": get_all_tags()})

    def _handle_get_progress(self, query):
        video_id = query.get("video_id", [None])[0]
        if video_id and video_id in progress_store:
            self._send_json(progress_store[video_id])
        else:
            self._send_json({"percent": 0, "status": "unknown"})

    def _handle_video_file(self, path):
        video_id = path.split("/")[-1]
        video_dir = VIDEOS_DIR / video_id
        if not video_dir.exists():
            self.send_error(404, "Video not found")
            return

        mp4_files = list(video_dir.glob("*.mp4"))
        if not mp4_files:
            self.send_error(404, "Video file not found")
            return

        fpath = mp4_files[0]
        size = fpath.stat().st_size

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

    def _handle_sound(self, path):
        """Serve .mp3 sound files from sounds/ directory."""
        filename = path.split("/")[-1]
        sound_dir = BASE_DIR / "sounds"
        sound_path = sound_dir / filename
        if not sound_path.exists():
            self.send_error(404, "Sound not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(sound_path.stat().st_size))
        self.end_headers()
        with open(sound_path, "rb") as f:
            self.wfile.write(f.read())

    def _handle_scan_videos(self):
        """List MP4 files in videos/ not yet in library."""
        video_dirs = [
            BASE_DIR / "videos",
            BASE_DIR / "videos" / "douyin",
        ]
        lib = load_library()
        lib_ids = {v.get("id", "") for v in lib.get("videos", [])}

        found = []
        for vdir in video_dirs:
            if not vdir.exists():
                continue
            for mp4 in vdir.rglob("*.mp4"):
                vid = None
                for part in mp4.stem.split("_"):
                    if part.isdigit() and len(part) >= 16:
                        vid = part
                        break
                if vid and vid in lib_ids:
                    continue
                found.append({
                    "filepath": str(mp4),
                    "filename": mp4.name,
                    "size_mb": round(mp4.stat().st_size / (1024 * 1024), 1),
                    "title": mp4.stem.rsplit("_", 1)[0] if "_" in mp4.stem else mp4.stem,
                    "video_id": vid or "",
                })
        self._send_json({"videos": found})

    def _handle_get_video(self, path, query):
        parts = path.split("/")
        video_id = parts[-1]
        sub_resource = parts[-2] if len(parts) >= 3 else None

        video_dir = VIDEOS_DIR / video_id

        if sub_resource == "report":
            report_path = video_dir / "deepseek_report.md"
            if report_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.end_headers()
                self.wfile.write(report_path.read_bytes())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.end_headers()
                self.wfile.write("".encode("utf-8"))
        elif sub_resource == "transcript":
            tp = video_dir / "transcript.json"
            if tp.exists():
                with open(tp, encoding="utf-8") as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"segments": [], "language": "", "duration": 0, "char_count": 0, "segment_count": 0})
        elif sub_resource == "analysis":
            ap = video_dir / "script_analysis.json"
            if ap.exists():
                with open(ap, encoding="utf-8") as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"char_count": 0, "chars_per_min": 0, "ai_keywords": 0, "emotion_keywords": 0, "tech_keywords": 0})
        else:
            self._send_json({"error": "Invalid video resource"}, 400)

    # ── POST handlers ───────────────────────────

    def _handle_download(self, body):
        url = body.get("url", "").strip()
        if not url:
            self._send_json({"error": "请提供视频链接"}, 400)
            return

        video_id = body.get("video_id") or str(int(time.time() * 1000))
        video_dir = VIDEOS_DIR / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        print(f"[download] {url} → {video_dir}")
        info = download_video(url, video_dir, video_id)

        # Rename dir to match actual video_id if different
        if info["video_id"] != video_id:
            new_dir = VIDEOS_DIR / info["video_id"]
            if new_dir.exists():
                shutil.rmtree(str(new_dir))
            video_dir.rename(new_dir)
            video_id = info["video_id"]
            video_dir = new_dir

        # Move file if needed (vdl.py may have subdirectory)
        all_mp4 = list(video_dir.rglob("*.mp4"))
        if all_mp4:
            target = video_dir / all_mp4[0].name
            if all_mp4[0].parent != video_dir:
                shutil.move(str(all_mp4[0]), str(target))
            # Remove empty subdirs
            for d in sorted(video_dir.rglob("*"), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()

        info["video_id"] = video_id
        self._send_json(info)

    def _handle_transcribe(self, body):
        video_id = body.get("video_id", "").strip()
        if not video_id:
            self._send_json({"error": "请提供 video_id"}, 400)
            return

        video_dir = VIDEOS_DIR / video_id
        mp4_files = list(video_dir.glob("*.mp4"))
        if not mp4_files:
            self._send_json({"error": "视频文件不存在，请先下载"}, 404)
            return

        print(f"[transcribe] {mp4_files[0]}")
        output = video_dir / "transcript.json"
        
        # Progress callback for real-time feedback
        progress_store[video_id] = {"percent": 0, "status": "transcribing", "step": "transcribe"}
        def on_progress(pct):
            progress_store[video_id] = {"percent": pct, "status": "transcribing", "step": "transcribe"}
        
        result = transcribe_video_file(mp4_files[0], output, progress_callback=on_progress)
        progress_store[video_id] = {"percent": 100, "status": "done", "step": "transcribe"}
        
        # Update library status
        lib = load_library()
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                v["transcript_status"] = "done"
                if not v.get("title") or v.get("title") == video_id:
                    v["title"] = result.get("title", video_id)
                break
        save_library(lib)
        
        self._send_json({
            "status": "done",
            "char_count": result["char_count"],
            "segment_count": result["segment_count"],
            "duration_sec": result["duration"],
            "language": result["language"],
        })

    def _handle_analyze(self, body):
        video_id = body.get("video_id", "").strip()
        if not video_id:
            self._send_json({"error": "请提供 video_id"}, 400)
            return

        print(f"[server {time.strftime('%H:%M:%S')}] analyze 开始: {video_id}")
        t0 = time.time()
        video_dir = VIDEOS_DIR / video_id

        # Load transcript
        transcript_path = video_dir / "transcript.json"
        if not transcript_path.exists():
            self._send_json({"error": "转写文件不存在，请先转写"}, 404)
            return

        with open(transcript_path, encoding="utf-8") as f:
            transcript = json.load(f)

        # Script analysis
        script_stats = analyze_transcript(transcript)
        if script_stats:
            analysis_path = video_dir / "script_analysis.json"
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(script_stats, f, ensure_ascii=False, indent=2)

        # Load video info from library
        lib = load_library()
        video_info = None
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                video_info = v
                break
        if not video_info:
            # Build minimal info
            lib_files = list(video_dir.glob("*.mp4"))
            video_info = {
                "title": lib_files[0].stem if lib_files else video_id,
                "platform": "unknown",
            }

        # Call DeepSeek
        print(f"[analyze] DeepSeek analysis for {video_id}")
        result = call_deepseek(video_info, transcript, script_stats)

        if result["error"]:
            self._send_json(result, 200)  # Return 200 with error info for frontend
            return

        # Save report
        report_path = video_dir / "deepseek_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(result["report"])

        # Update tags
        if result["tags"]:
            update_tags_system(result["tags"])

        # Update library entry
        updated = False
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                v["tags"] = result["tags"]
                v["viral_score"] = result["viral_score"]
                v["deepseek_status"] = "done"
                v["transcript_status"] = "done"
                v["analysis_status"] = "done"
                if script_stats:
                    v["script_stats"] = script_stats
                    v["duration_sec"] = script_stats["duration"]
                updated = True
                break

        if not updated:
            # New entry
            lib["videos"].append({
                "id": video_id,
                "url": video_info.get("url", ""),
                "title": video_info.get("title", ""),
                "platform": video_info.get("platform", "unknown"),
                "duration_sec": script_stats["duration"] if script_stats else 0,
                "file_size_mb": video_info.get("file_size_mb", 0),
                "tags": result["tags"],
                "viral_score": result["viral_score"],
                "script_stats": script_stats,
                "deepseek_status": "done",
                "transcript_status": "done",
                "analysis_status": "done",
                "metrics": video_info.get("metrics", {}),
                "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            })

        save_library(lib)

        self._send_json({
            "status": "done",
            "viral_score": result["viral_score"],
            "tags": result["tags"],
        })

    def _handle_pipeline(self, body):
        """Full pipeline: download → transcribe → analyze."""
        url = body.get("url", "").strip()
        mode = body.get("mode", "full")  # full | download_transcribe | download_only
        video_id = body.get("video_id", str(int(time.time() * 1000)))

        if not url:
            self._send_json({"error": "请提供视频链接"}, 400)
            return

        print(f"[server {time.strftime('%H:%M:%S')}] ═══ pipeline 开始: {video_id}, mode={mode} ═══")
        pipe_t0 = time.time()
        video_dir = VIDEOS_DIR / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        steps = []
        old_vid = None  # track original video_id for progress key mapping

        # Step 1: Download
        try:
            print(f"[server {time.strftime('%H:%M:%S')}] [pipeline] Step 1/4: Download {url[:80]}")
            info = download_video(url, video_dir, video_id)
            if info["video_id"] != video_id:
                old_vid = video_id
                new_dir = VIDEOS_DIR / info["video_id"]
                if new_dir.exists():
                    shutil.rmtree(str(new_dir))
                video_dir.rename(new_dir)
                video_id = info["video_id"]
                video_dir = new_dir
                # Copy progress to new video_id, keep old for frontend polling
                if old_vid in progress_store:
                    progress_store[video_id] = dict(progress_store[old_vid])

            # Flatten files
            all_mp4 = list(video_dir.rglob("*.mp4"))
            if all_mp4 and all_mp4[0].parent != video_dir:
                shutil.move(str(all_mp4[0]), str(video_dir / all_mp4[0].name))
            for d in sorted(video_dir.rglob("*"), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()

            steps.append({"step": "download", "status": "done", "info": info})
        except Exception as e:
            steps.append({"step": "download", "status": "error", "error": str(e)})
            self._send_json({"status": "error", "steps": steps, "video_id": video_id}, 200)
            return

        if mode == "download_only":
            # Save to library and return
            self._save_pipeline_to_library(video_id, video_dir, info, steps, None, None)
            print(f"[server {time.strftime('%H:%M:%S')}] pipeline 完成 (download_only), 总耗时 {time.time()-pipe_t0:.1f}s")
            self._send_json({"status": "done", "steps": steps, "video_id": video_id})
            return

        # Step 2: Transcribe
        transcript = None
        try:
            print(f"[server {time.strftime('%H:%M:%S')}] [pipeline] Step 2/4: Transcribe {video_id}")
            mp4_files = list(video_dir.glob("*.mp4"))
            output = video_dir / "transcript.json"
            progress_store[video_id] = {"percent": 0, "status": "transcribing", "step": "transcribe"}
            def on_pipe_progress(pct):
                entry = {"percent": pct, "status": "transcribing", "step": "transcribe"}
                progress_store[video_id] = entry
                if old_vid:
                    progress_store[old_vid] = entry
            transcript = transcribe_video_file(mp4_files[0], output, progress_callback=on_pipe_progress)
            done_entry = {"percent": 100, "status": "done", "step": "transcribe"}
            progress_store[video_id] = done_entry
            if old_vid:
                progress_store[old_vid] = done_entry
            steps.append({"step": "transcribe", "status": "done",
                          "char_count": transcript["char_count"], "duration": transcript["duration"]})
        except Exception as e:
            print(f"[server {time.strftime('%H:%M:%S')}] [pipeline] Transcribe FAILED: {e}")
            traceback.print_exc()
            steps.append({"step": "transcribe", "status": "error", "error": str(e)})
            self._send_json({"status": "error", "steps": steps, "video_id": video_id}, 200)
            return

        # Step 3: Script analysis
        script_stats = None
        if transcript:
            script_stats = analyze_transcript(transcript)
            if script_stats:
                analysis_path = video_dir / "script_analysis.json"
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump(script_stats, f, ensure_ascii=False, indent=2)
            steps.append({"step": "script_analysis", "status": "done"})

        if mode == "download_transcribe":
            self._save_pipeline_to_library(video_id, video_dir, info, steps, transcript, script_stats)
            print(f"[server {time.strftime('%H:%M:%S')}] pipeline 完成 (download_transcribe), 总耗时 {time.time()-pipe_t0:.1f}s")
            self._send_json({"status": "done", "steps": steps, "video_id": video_id})
            return

        # Step 4: DeepSeek AI analysis
        video_info = {"title": info.get("title", ""), "platform": info.get("platform", "unknown"),
                      "url": url, "file_size_mb": info.get("file_size_mb", 0)}
        try:
            print(f"[server {time.strftime('%H:%M:%S')}] [pipeline] Step 4/4: AI Analysis {video_id}")
            progress_store[video_id] = {"percent": 50, "status": "analyzing", "step": "analyze"}
            if old_vid:
                progress_store[old_vid] = {"percent": 50, "status": "analyzing", "step": "analyze"}
            deepseek_result = call_deepseek(video_info, transcript, script_stats)
            if deepseek_result.get("error"):
                progress_store[video_id] = {"percent": 100, "status": "error", "step": "analyze"}
                steps.append({"step": "ai_analysis", "status": "error", "error": deepseek_result["error"]})
            else:
                progress_store[video_id] = {"percent": 100, "status": "done", "step": "analyze"}
                report_path = video_dir / "deepseek_report.md"
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(deepseek_result["report"])
                if deepseek_result.get("tags"):
                    update_tags_system(deepseek_result["tags"])
                steps.append({"step": "ai_analysis", "status": "done",
                              "viral_score": deepseek_result["viral_score"], "tags": deepseek_result["tags"]})
        except Exception as e:
            print(f"[server {time.strftime('%H:%M:%S')}] [pipeline] AI Analysis FAILED: {e}")
            traceback.print_exc()
            progress_store[video_id] = {"percent": 100, "status": "error", "step": "analyze"}
            steps.append({"step": "ai_analysis", "status": "error", "error": str(e)})

        self._save_pipeline_to_library(video_id, video_dir, info, steps, transcript, script_stats, deepseek_result if 'deepseek_result' in dir() else None)
        print(f"[server {time.strftime('%H:%M:%S')}] ═══ pipeline 完成, 总耗时 {time.time()-pipe_t0:.1f}s ═══")
        self._send_json({"status": "done", "steps": steps, "video_id": video_id})

    def _save_pipeline_to_library(self, video_id, video_dir, info, steps, transcript=None, script_stats=None, deepseek_result=None):
        """Save pipeline result to library.json."""
        lib = load_library()

        # Find or create entry
        entry = None
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                entry = v
                break

        if not entry:
            entry = {
                "id": video_id,
                "url": info.get("url", ""),
                "title": info.get("title", ""),
                "platform": info.get("platform", "unknown"),
                "file_size_mb": info.get("file_size_mb", 0),
                "download_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "transcript_status": "pending",
                "analysis_status": "pending",
                "deepseek_status": "pending",
                "tags": [],
                "viral_score": 0,
                "metrics": {},
                "script_stats": {},
                "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
            lib["videos"].append(entry)

        if transcript:
            entry["transcript_status"] = "done"
            entry["script_stats"] = script_stats or {}
            entry["duration_sec"] = transcript.get("duration", 0)

        if deepseek_result and not deepseek_result.get("error"):
            entry["deepseek_status"] = "done"
            entry["analysis_status"] = "done"
            entry["tags"] = deepseek_result.get("tags", [])
            entry["viral_score"] = deepseek_result.get("viral_score", 0)
        elif deepseek_result and deepseek_result.get("error"):
            entry["deepseek_status"] = "error"

        save_library(lib)

    def _handle_batch_analyze(self, body):
        video_ids = body.get("video_ids", [])
        if not video_ids:
            self._send_json({"error": "请提供 video_ids 列表"}, 400)
            return

        results = []
        for vid in video_ids:
            try:
                self._handle_analyze({"video_id": vid})
                results.append({"video_id": vid, "status": "done"})
            except Exception as e:
                results.append({"video_id": vid, "status": "error", "error": str(e)})

        self._send_json({"status": "done", "results": results, "total": len(video_ids)})

    def _handle_save(self, body):
        """Save/update video entry in library."""
        video_id = body.get("id", "")
        if not video_id:
            self._send_json({"error": "请提供 video id"}, 400)
            return

        lib = load_library()
        updated = False
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                for key in ("title", "tags", "url", "platform", "viral_score", "metrics"):
                    if key in body:
                        v[key] = body[key]
                updated = True
                break

        if not updated:
            lib["videos"].append(body)

        save_library(lib)
        self._send_json({"status": "saved"})

    def _handle_delete(self, body):
        video_id = body.get("id", "")
        if not video_id:
            self._send_json({"error": "请提供 video id"}, 400)
            return

        # Load library and find the video to get its tags
        lib = load_library()
        target_tags = []
        for v in lib.get("videos", []):
            if v.get("id") == video_id:
                target_tags = v.get("tags", [])
                break

        # Remove from library
        lib["videos"] = [v for v in lib.get("videos", []) if v.get("id") != video_id]
        save_library(lib)

        # Clean up tags.json — decrement counts for removed video's tags
        if target_tags:
            tags_data = load_tags()
            all_tags = tags_data.get("tags", {})
            for t in target_tags:
                if t in all_tags:
                    all_tags[t] = max(0, all_tags[t] - 1)
                    if all_tags[t] <= 0:
                        del all_tags[t]
            tags_data["tags"] = all_tags
            save_tags(tags_data)

        # Remove files (best-effort; video may be in use)
        video_dir = VIDEOS_DIR / video_id
        if video_dir.exists():
            try:
                shutil.rmtree(str(video_dir))
            except Exception as e:
                print(f"[server] 删除目录失败 (可忽略): {video_dir} - {e}")

        self._send_json({"status": "deleted"})

    def _handle_tags(self, body):
        """Tag CRUD: rename, delete, merge."""
        action = body.get("action", "")
        tag = body.get("tag", "").strip()
        new_tag = body.get("new_tag", "").strip()

        if not action or not tag:
            self._send_json({"error": "请提供 action 和 tag 参数"}, 400)
            return

        tags_data = load_tags()
        all_tags = tags_data.get("tags", {})

        if action == "rename":
            if not new_tag or new_tag == tag:
                self._send_json({"error": "新标签名不能为空或相同"}, 400)
                return
            if tag in all_tags:
                count = all_tags.pop(tag)
                all_tags[new_tag] = all_tags.get(new_tag, 0) + count
                tags_data["tags"] = all_tags
                save_tags(tags_data)
                # Also update library.json
                lib = load_library()
                for v in lib.get("videos", []):
                    if tag in v.get("tags", []):
                        v["tags"] = [new_tag if x == tag else x for x in v["tags"]]
                save_library(lib)
                self._send_json({"status": "renamed", "count": count})
            else:
                self._send_json({"error": "标签不存在"}, 404)

        elif action == "delete":
            if tag in all_tags:
                count = all_tags.pop(tag)
                tags_data["tags"] = all_tags
                save_tags(tags_data)
                # Remove tag from all videos in library
                lib = load_library()
                for v in lib.get("videos", []):
                    if tag in v.get("tags", []):
                        v["tags"] = [x for x in v["tags"] if x != tag]
                save_library(lib)
                self._send_json({"status": "deleted", "count": count})
            else:
                self._send_json({"error": "标签不存在"}, 404)

        elif action == "merge":
            into = body.get("into", "").strip()
            if not into:
                self._send_json({"error": "请提供 into 参数（合并目标标签）"}, 400)
                return
            if tag not in all_tags:
                self._send_json({"error": f"标签 '{tag}' 不存在"}, 404)
                return
            src_count = all_tags.pop(tag)
            all_tags[into] = all_tags.get(into, 0) + src_count
            tags_data["tags"] = all_tags
            save_tags(tags_data)
            # Replace in library
            lib = load_library()
            for v in lib.get("videos", []):
                if tag in v.get("tags", []):
                    v["tags"] = list(set([into if x == tag else x for x in v["tags"]]))
            save_library(lib)
            self._send_json({"status": "merged", "count": src_count, "into": into})

        else:
            self._send_json({"error": f"未知操作: {action}，支持: rename, delete, merge"}, 400)

    def _handle_import_video(self, body):
        """Import a video from the global videos/ directory into library."""
        filepath = body.get("filepath", "").strip()
        title = body.get("title", "").strip()
        if not filepath:
            self._send_json({"error": "请提供 filepath 参数"}, 400)
            return

        src = Path(filepath)
        if not src.exists():
            self._send_json({"error": f"文件不存在: {filepath}"}, 404)
            return

        # Generate video_id and copy to library
        video_id = src.stem.split("_")[-1] if "_" in src.stem else src.stem[:16]
        # Try to extract douyin ID from filename like: ..._7643631135368449286.mp4
        for part in src.stem.split("_"):
            if part.isdigit() and len(part) >= 16:
                video_id = part
                break

        dest_dir = VIDEOS_DIR / video_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / src.name
        if not dest_file.exists():
            shutil.copy2(src, dest_file)

        file_size = src.stat().st_size / (1024 * 1024)

        # Add to library
        lib = load_library()
        existing = [v for v in lib.get("videos", []) if v.get("id") == video_id]
        if existing:
            self._send_json({"error": f"视频 {video_id} 已在库中"}, 409)
            return

        lib["videos"].append({
            "id": video_id,
            "title": title or src.stem.rsplit("_", 1)[0],
            "url": "file://" + str(src),
            "platform": "unknown",
            "duration_sec": 0,
            "file_size_mb": round(file_size, 1),
            "download_time": datetime.utcnow().isoformat() + "Z",
            "transcript_status": "pending",
            "analysis_status": "pending",
            "deepseek_status": "pending",
            "tags": [],
            "metrics": {"likes": 0, "comments": 0, "shares": 0, "collects": 0},
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        save_library(lib)

        self._send_json({"status": "imported", "video_id": video_id, "title": title or src.stem})

    # ── Helpers ─────────────────────────────────

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default logs


# ── Main ───────────────────────────────────────────

if __name__ == "__main__":
    print(f"=" * 60)
    print(f"  Video Script Analyzer Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Library: {LIBRARY_DIR}")
    print(f"=" * 60)

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print(f"  ⚠ DEEPSEEK_API_KEY 未设置，AI 分析功能不可用")
        print(f"  → 设置方式: set DEEPSEEK_API_KEY=sk-xxx")

    print(f"  Ctrl+C to stop")
    print(f"=" * 60)

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        """Multi-threaded HTTP server to handle concurrent requests (progress polling during pipeline)."""
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", PORT), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
