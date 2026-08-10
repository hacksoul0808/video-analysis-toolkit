"""
静态文件 Handler：SPA 首页、视频文件（支持 Range 请求）、音频文件、转写/分析数据、Web 静态资源。
"""
import json
import re
import mimetypes
from pathlib import Path
from server.config import WEB_DIR, VIDEOS_DIR, PORT

MIME_TYPES = {
    ".css": "text/css",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".html": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".json": "application/json",
    ".md": "text/markdown",
}

_mime_initialized = False


def _init_mime():
    """补注册缺失的 MIME 类型到标准库。"""
    global _mime_initialized
    if _mime_initialized:
        return
    _mime_initialized = True
    for ext, mime in MIME_TYPES.items():
        mimetypes.add_type(mime, ext)


def handle_static(handler):
    """GET /css/*, /js/*, /assets/* — 提供 Web 目录中的静态文件。"""
    path = handler.path.lstrip("/")
    file_path = WEB_DIR / path

    # 安全检查：防止路径遍历
    try:
        file_path.relative_to(WEB_DIR)
    except ValueError:
        handler.send_error(403, "Forbidden")
        return

    if not file_path.exists() or not file_path.is_file():
        handler.send_error(404, "Not found")
        return

    # 直接按扩展名查找 MIME 类型（不用系统注册表，避免 Windows 下 .js → text/plain）
    ext = file_path.suffix.lower()
    content_type = MIME_TYPES.get(ext, "application/octet-stream")

    size = file_path.stat().st_size
    handler.send_response(200)
    handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
    handler.send_header("Content-Length", str(size))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    with open(file_path, "rb") as f:
        handler.wfile.write(f.read())


def handle_index(handler):
    """GET / — 提供 SPA 首页。"""
    html_path = WEB_DIR / "index.html"
    if not html_path.exists():
        handler.send_response(500)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": "web/index.html not found"}, ensure_ascii=False).encode("utf-8"))
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    with open(html_path, "rb") as f:
        handler.wfile.write(f.read())


def handle_video_file(handler):
    """GET /api/video-file/{video_id} — 提供视频文件（支持 Range 请求）。"""
    path = handler.path
    video_id = path.split("/")[-1]
    video_dir = VIDEOS_DIR / video_id
    if not video_dir.exists():
        handler.send_error(404, "Video not found")
        return

    mp4_files = list(video_dir.glob("*.mp4"))
    if not mp4_files:
        handler.send_error(404, "Video file not found")
        return

    fpath = mp4_files[0]
    size = fpath.stat().st_size

    range_header = handler.headers.get("Range")
    if range_header:
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))
        length = end - start + 1
        handler.send_response(206)
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        handler.send_header("Content-Length", str(length))
        handler.send_header("Content-Type", "video/mp4")
        handler.send_header("Accept-Ranges", "bytes")
        handler.end_headers()
        with open(fpath, "rb") as f:
            f.seek(start)
            handler.wfile.write(f.read(length))
    else:
        handler.send_response(200)
        handler.send_header("Content-Type", "video/mp4")
        handler.send_header("Content-Length", str(size))
        handler.send_header("Accept-Ranges", "bytes")
        handler.end_headers()
        with open(fpath, "rb") as f:
            while chunk := f.read(65536):
                handler.wfile.write(chunk)


def handle_sound(handler):
    """GET /sounds/{filename} — 提供音频文件。"""
    filename = handler.path.split("/")[-1]
    sound_dir = WEB_DIR / "assets" / "sounds"
    sound_path = sound_dir / filename
    if not sound_path.exists():
        handler.send_error(404, "Sound not found")
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "audio/mpeg")
    handler.send_header("Content-Length", str(sound_path.stat().st_size))
    handler.end_headers()
    with open(sound_path, "rb") as f:
        handler.wfile.write(f.read())


def handle_video_resource(handler):
    """GET /api/video/{resource}/{video_id} — 提供转写/分析/报告数据。"""
    path = handler.path
    parts = path.split("/")
    video_id = parts[-1]
    sub_resource = parts[-2] if len(parts) >= 3 else None
    video_dir = VIDEOS_DIR / video_id

    if sub_resource == "report":
        report_path = video_dir / "deepseek_report.md"
        handler.send_response(200)
        handler.send_header("Content-Type", "text/markdown; charset=utf-8")
        handler.end_headers()
        if report_path.exists():
            handler.wfile.write(report_path.read_bytes())
        else:
            handler.wfile.write("".encode("utf-8"))

    elif sub_resource == "transcript":
        tp = video_dir / "transcript.json"
        if tp.exists():
            with open(tp, encoding="utf-8") as f:
                _send_json(handler, json.load(f))
        else:
            _send_json(handler, {"segments": [], "language": "", "duration": 0, "char_count": 0, "segment_count": 0})

    elif sub_resource == "analysis":
        ap = video_dir / "script_analysis.json"
        if ap.exists():
            with open(ap, encoding="utf-8") as f:
                _send_json(handler, json.load(f))
        else:
            _send_json(handler, {"char_count": 0, "chars_per_min": 0, "ai_keywords": 0, "emotion_keywords": 0, "tech_keywords": 0})

    elif sub_resource == "cover":
        cover_path = video_dir / "cover.jpg"
        if cover_path.exists():
            handler.send_response(200)
            handler.send_header("Content-Type", "image/jpeg")
            handler.send_header("Content-Length", str(cover_path.stat().st_size))
            handler.send_header("Cache-Control", "public, max-age=3600")
            handler.end_headers()
            with open(cover_path, "rb") as f:
                handler.wfile.write(f.read())
        else:
            handler.send_error(404, "Cover not found")

    else:
        _send_json(handler, {"error": "Invalid video resource"}, 400)


def _send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except OSError:
        pass
