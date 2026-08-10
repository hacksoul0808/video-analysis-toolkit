"""
Metrics 刷新 Handler：POST /api/refresh-metrics
对 library.json 中已有的视频批量补抓互动数据（点赞/评论/分享/播放/收藏）。
"""
import json
import re
import time
from server.repository import load_library, save_library


def handle_refresh_metrics(handler, body: dict):
    """POST /api/refresh-metrics
    Body: { "video_ids": [...] }   // 可选，不传则刷新所有 douyin 视频
    """
    lib = load_library()
    videos = lib.get("videos", [])

    target_ids = body.get("video_ids")
    if target_ids:
        target_videos = [v for v in videos if v.get("id") in target_ids]
    else:
        target_videos = [v for v in videos if v.get("platform") == "douyin"]

    total = len(target_videos)
    updated = 0
    failed = 0
    details = []

    for v in target_videos:
        vid = v.get("id", "")
        result = _fetch_metrics(vid)
        if result:
            v["metrics"] = result
            updated += 1
            details.append({"video_id": vid, "status": "updated", "metrics": result})
        else:
            failed += 1
            details.append({"video_id": vid, "status": "failed", "error": "statistics not found"})
        time.sleep(1.5)  # 避免请求过快被限流

    if updated > 0:
        save_library(lib)

    _send_json(handler, {
        "status": "done",
        "total": total,
        "updated": updated,
        "failed": failed,
        "details": details,
    })


def _fetch_metrics(video_id: str) -> dict | None:
    """访问 iesdouyin 分享页提取 statistics。返回 metrics dict 或 None。"""
    try:
        from curl_cffi import requests as cf_requests

        session = cf_requests.Session(impersonate="chrome120")
        url = f"https://www.iesdouyin.com/share/video/{video_id}/"
        resp = session.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        })

        m = re.search(r'"statistics"\s*:\s*\{[^}]+\}', resp.text)
        if not m:
            return None

        stats_block = '{' + m.group(0) + '}'
        raw = json.loads(stats_block)
        stats = raw.get("statistics", {})

        if not stats:
            return None

        return {
            "likes": stats.get("digg_count", 0),
            "comments": stats.get("comment_count", 0),
            "shares": stats.get("share_count", 0),
            "plays": stats.get("play_count", 0),
            "collects": stats.get("collect_count", 0),
        }
    except Exception:
        return None


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
