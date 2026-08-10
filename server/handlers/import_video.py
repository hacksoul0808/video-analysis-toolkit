"""
视频导入 Handler：GET /api/scan-videos, POST /api/import。
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
from server.config import DATA_DIR, VIDEOS_DIR
from server.repository import load_library, save_library


def handle_scan(handler):
    """GET /api/scan-videos — 扫描未入库的 MP4 文件。"""
    video_dirs = [DATA_DIR, VIDEOS_DIR]
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
    _send_json(handler, {"videos": found})


def handle_import(handler, body: dict):
    """POST /api/import — 导入本地视频到 library。"""
    filepath = body.get("filepath", "").strip()
    title = body.get("title", "").strip()
    if not filepath:
        return _send_json(handler, {"error": "请提供 filepath 参数"}, 400)

    src = Path(filepath)
    if not src.exists():
        return _send_json(handler, {"error": f"文件不存在: {filepath}"}, 404)

    video_id = src.stem.split("_")[-1] if "_" in src.stem else src.stem[:16]
    for part in src.stem.split("_"):
        if part.isdigit() and len(part) >= 16:
            video_id = part
            break

    dest_dir = VIDEOS_DIR / video_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / src.name
    if not dest_file.exists():
        shutil.copy2(src, dest_file)

    file_size = round(src.stat().st_size / (1024 * 1024), 1)

    lib = load_library()
    existing = [v for v in lib.get("videos", []) if v.get("id") == video_id]
    if existing:
        return _send_json(handler, {"error": f"视频 {video_id} 已在库中"}, 409)

    lib["videos"].append({
        "id": video_id,
        "title": title or src.stem.rsplit("_", 1)[0],
        "url": "file://" + str(src),
        "platform": "unknown",
        "duration_sec": 0,
        "file_size_mb": file_size,
        "download_time": datetime.utcnow().isoformat() + "Z",
        "transcript_status": "pending",
        "analysis_status": "pending",
        "deepseek_status": "pending",
        "tags": [],
        "metrics": {"likes": 0, "comments": 0, "shares": 0, "collects": 0},
        "created_at": datetime.utcnow().isoformat() + "Z",
    })
    save_library(lib)

    _send_json(handler, {"status": "imported", "video_id": video_id, "title": title or src.stem})


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
