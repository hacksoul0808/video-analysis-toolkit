"""
排行榜 Handler：GET /api/ranking/{platform}, POST /api/ranking/batch-download,
GET /api/ranking/batch-progress, POST /api/ranking/{platform}/refresh。
"""
import json
from urllib.parse import parse_qs

from server.services.ranking_service import (
    get_ranking, batch_download, get_batch_progress, force_refresh
)


def handle_get_ranking(handler):
    """GET /api/ranking/{platform}?page=1&page_size=50"""
    path = handler.parsed.path
    # 从路径提取 platform: /api/ranking/douyin → "douyin"
    parts = path.strip("/").split("/")
    platform = parts[2] if len(parts) >= 3 else "douyin"

    query = parse_qs(handler.parsed.query)
    page = int(query.get("page", ["1"])[0])
    page_size = int(query.get("page_size", ["50"])[0])
    page_size = min(page_size, 100)

    result = get_ranking(platform, page, page_size)
    _send_json(handler, result)


def handle_batch_download(handler, body: dict):
    """POST /api/ranking/batch-download"""
    platform = body.get("platform", "douyin")
    video_ids = body.get("video_ids", [])
    auto_analyze = body.get("auto_analyze", False)

    if not video_ids:
        return _send_json(handler, {"error": "请提供要下载的视频列表"}, 400)

    result = batch_download(platform, video_ids, auto_analyze)
    _send_json(handler, result)


def handle_batch_progress(handler):
    """GET /api/ranking/batch-progress?platform=douyin"""
    query = parse_qs(handler.parsed.query)
    platform = query.get("platform", ["douyin"])[0]

    result = get_batch_progress(platform)
    _send_json(handler, result)


def handle_refresh_ranking(handler):
    """POST /api/ranking/{platform}/refresh"""
    path = handler.parsed.path
    parts = path.strip("/").split("/")
    platform = parts[2] if len(parts) >= 3 else "douyin"

    result = force_refresh(platform)
    _send_json(handler, result)


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
