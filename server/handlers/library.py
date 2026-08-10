"""
库管理 Handler：GET /api/library, GET /api/stats, GET /api/methodology,
POST /api/save, POST /api/delete。
"""
import json
from urllib.parse import parse_qs
from server.repository import load_library, save_library, find_video, get_all_tags, decrement_tags
from server.services.stats import compute_stats
from server.services.methodology import aggregate_methodology
from server.config import VIDEOS_DIR, WEB_DIR
import shutil


def handle_get_library(handler):
    """GET /api/library?sort=&tag=&q="""
    query = parse_qs(handler.parsed.query)
    lib = load_library()
    videos = lib.get("videos", [])

    tag = query.get("tag", [None])[0]
    if tag:
        videos = [v for v in videos if tag in v.get("tags", [])]

    q = query.get("q", [None])[0]
    if q:
        q_lower = q.lower()
        filtered = []
        for v in videos:
            if q_lower in (v.get("title", "") or v.get("id", "")).lower():
                filtered.append(v)
                continue
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

    sort = query.get("sort", ["created_at"])[0]
    if sort == "likes":
        videos.sort(key=lambda x: x.get("metrics", {}).get("likes", 0), reverse=True)
    elif sort == "viral_score":
        videos.sort(key=lambda x: x.get("viral_score", 0), reverse=True)
    elif sort == "duration":
        videos.sort(key=lambda x: x.get("duration_sec", 0), reverse=True)
    else:
        videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    _send_json(handler, {"videos": videos, "total": len(videos), "tags": get_all_tags()})


def handle_stats(handler):
    """GET /api/stats"""
    lib = load_library()
    _send_json(handler, compute_stats(lib.get("videos", [])))


def handle_methodology(handler):
    """GET /api/methodology?tag="""
    query = parse_qs(handler.parsed.query)
    tag = query.get("tag", [None])[0]
    lib = load_library()
    _send_json(handler, aggregate_methodology(lib, tag))


def handle_save(handler, body: dict):
    """POST /api/save"""
    video_id = body.get("id", "")
    if not video_id:
        return _send_json(handler, {"error": "请提供 video id"}, 400)

    lib = load_library()
    for v in lib.get("videos", []):
        if v.get("id") == video_id:
            for key in ("title", "tags", "url", "platform", "viral_score", "metrics"):
                if key in body:
                    v[key] = body[key]
            save_library(lib)
            return _send_json(handler, {"status": "saved"})

    lib.setdefault("videos", []).append(body)
    save_library(lib)
    _send_json(handler, {"status": "saved"})


def handle_delete(handler, body: dict):
    """POST /api/delete"""
    video_id = body.get("id", "")
    if not video_id:
        return _send_json(handler, {"error": "请提供 video id"}, 400)

    lib = load_library()
    target_tags = []
    for v in lib.get("videos", []):
        if v.get("id") == video_id:
            target_tags = v.get("tags", [])
            break

    lib["videos"] = [v for v in lib.get("videos", []) if v.get("id") != video_id]
    save_library(lib)

    if target_tags:
        decrement_tags(target_tags)

    video_dir = VIDEOS_DIR / video_id
    if video_dir.exists():
        try:
            shutil.rmtree(str(video_dir))
        except Exception as e:
            print(f"[library] 删除目录失败 (可忽略): {video_dir} - {e}")

    _send_json(handler, {"status": "deleted"})


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
