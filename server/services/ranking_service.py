"""
排行榜服务：排行数据采集 + 缓存 + 批量下载队列。
"""
import json
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

from server.config import DATA_DIR, VIDEOS_DIR, SCRIPTS_DIR
from server.repository import load_library, save_library, find_video

# ── 缓存路径 ──
RANKING_CACHE_FILE = DATA_DIR / "ranking_cache.json"
RANKING_CACHE_TTL_SECONDS = 30 * 60      # 30分钟
RANKING_CACHE_MAX_AGE_SECONDS = 2 * 60 * 60  # 2小时

# ── Cookie 配置 ──
DOUYIN_COOKIE = os.environ.get("DOUYIN_COOKIE", "").strip()
HAS_COOKIE = bool(DOUYIN_COOKIE)

# ── 批量下载队列 (模块级，进程内共享) ──
_batch_queues: dict[str, dict] = {}       # key: platform, value: { total, completed, downloading, failed, items, updated_at }
_batch_lock = threading.Lock()

# ── 后台刷新锁 ──
_refresh_locks: dict[str, threading.Lock] = {}
_refresh_locks_lock = threading.Lock()


def _get_platform_lock(platform: str) -> threading.Lock:
    with _refresh_locks_lock:
        if platform not in _refresh_locks:
            _refresh_locks[platform] = threading.Lock()
        return _refresh_locks[platform]


# ═══════════════════════════════════════════════════════
# 缓存读取
# ═══════════════════════════════════════════════════════

def _load_cache() -> dict:
    if RANKING_CACHE_FILE.exists():
        with open(RANKING_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(data: dict):
    RANKING_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RANKING_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_cache_age_seconds(platform: str) -> float | None:
    """返回缓存年龄(秒)，无缓存返回 None。"""
    cache = _load_cache()
    plat = cache.get(platform)
    if not plat or not plat.get("updated_at"):
        return None
    try:
        updated = datetime.fromisoformat(plat["updated_at"])
        return (datetime.now(timezone.utc) - updated.replace(tzinfo=timezone.utc)).total_seconds()
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════
# 排行采集核心 — 爆款视频（非热搜新闻）
# ═══════════════════════════════════════════════════════

# 爆款视频常用搜索词（内容类，非新闻类）
_VIRAL_SEARCH_KEYWORDS = [
    "搞笑", "日常", "剧情", "反转", "挑战",
    "教程", "干货", "冷知识", "测评", "对比",
    "推荐", "好物", "穿搭", "美食", "旅行",
    "情感", "职场", "成长", "创业", "治愈",
]

_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
}

# 如果配置了Cookie，加到请求头
if HAS_COOKIE:
    _COMMON_HEADERS["Cookie"] = DOUYIN_COOKIE


def _viral_score(stats: dict) -> float:
    """计算综合爆款指数（点赞3分 + 分享5分 + 评论2分 + 收藏1分 + 播放1分）。"""
    digg = stats.get("digg_count", 0) or 0
    share = stats.get("share_count", 0) or 0
    comment = stats.get("comment_count", 0) or 0
    collect = stats.get("collect_count", 0) or 0
    play = stats.get("play_count", 0) or 0
    return digg * 3 + share * 5 + comment * 2 + collect * 1 + play * 0.1


def _get_hot_keywords() -> list[str]:
    """从热搜榜获取当前热点关键词（内容向过滤）。"""
    try:
        import urllib.request
        import urllib.parse

        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/?"
        url += urllib.parse.urlencode({
            "detail_list": "1", "source": "6",
            "board_type": "0", "board_sub_type": "",
            "version_code": "170400", "version_name": "17.4.0",
            "device_platform": "webapp", "aid": "6383",
            "channel": "channel_pc_web",
        })
        req = urllib.request.Request(url, headers={
            **_COMMON_HEADERS, "Referer": "https://www.douyin.com/discover"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        word_list = data.get("data", {}).get("word_list", [])
        keywords = []
        # 新闻过滤词
        news_filter = {"地震", "死亡", "事故", "火灾", "暴雨", "台风", "官方", "通报",
                       "政策", "习近平", "主席", "总理", "会议", "发布", "声明"}
        for item in word_list[:30]:
            word = item.get("word", "")
            if len(word) < 2:
                continue
            # 跳过纯新闻/时政
            if any(f in word for f in news_filter):
                continue
            keywords.append(word)
        return keywords[:15] if keywords else _VIRAL_SEARCH_KEYWORDS[:10]
    except Exception:
        return _VIRAL_SEARCH_KEYWORDS[:10]


def _search_videos(keyword: str, count: int = 15) -> list[dict]:
    """按关键词搜索视频（最多点赞 + ≤1分钟）。返回 aweme 列表。"""
    try:
        import urllib.request
        import urllib.parse

        url = "https://www.douyin.com/aweme/v1/web/search/item/?"
        url += urllib.parse.urlencode({
            "keyword": keyword,
            "search_channel": "aweme_video_web",
            "enable_history": "1",
            "search_source": "switch_tab",
            "query_correct_type": "1",
            "is_filter_search": "1",
            "sort_type": "1",           # 最多点赞
            "filter_duration": "0-1",   # 1分钟以内
            "offset": "0",
            "count": str(count),
            "version_code": "170400",
            "version_name": "17.4.0",
            "device_platform": "webapp",
            "aid": "6383",
        })
        req = urllib.request.Request(url, headers={
            **_COMMON_HEADERS,
            "Referer": f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}?type=video"
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("data", []) or []
    except Exception:
        return []


def _extract_video_info(aweme: dict, rank_base: int) -> dict | None:
    """从 aweme 对象提取排行所需的字段。"""
    aweme_id = str(aweme.get("aweme_id", ""))
    if not aweme_id:
        return None
    duration = aweme.get("duration", 0) // 1000 if aweme.get("duration") else 0
    if duration > 60:
        return None

    stats = aweme.get("statistics", {})
    author_info = aweme.get("author", {})
    video_info = aweme.get("video", {})
    cover_info = video_info.get("cover", {}) if video_info else {}
    url_list = cover_info.get("url_list", []) if cover_info else []
    desc = aweme.get("desc", "") or aweme.get("preview_title", "")
    text_extra = aweme.get("text_extra", []) or []

    return {
        "id": aweme_id,
        "rank": rank_base,
        "title": desc[:200],
        "author": author_info.get("nickname", "未知作者") if author_info else "未知作者",
        "play_count": stats.get("play_count", 0) or 0,
        "digg_count": stats.get("digg_count", 0) or 0,
        "share_count": stats.get("share_count", 0) or 0,
        "comment_count": stats.get("comment_count", 0) or 0,
        "collect_count": stats.get("collect_count", 0) or 0,
        "duration_sec": duration,
        "cover_url": url_list[0] if url_list else "",
        "tags": [t.get("hashtag_name", "") or t.get("tag_name", "") for t in text_extra if
                 t.get("hashtag_name") or t.get("tag_name")][:5],
        "platform": "douyin",
        "share_url": aweme.get("share_url", "") or f"https://www.douyin.com/video/{aweme_id}",
    }


def _fetch_douyin_viral() -> dict:
    """采集抖音爆款视频。
    
    有 Cookie：直接按热门内容关键词搜索视频，按爆款指数排序。
    无 Cookie：热搜 API 无法返回视频数据，提示配置 Cookie。
    """
    if not HAS_COOKIE:
        return {
            "videos": [],
            "error": "需要配置抖音 Cookie 才能获取爆款视频。请在 .env 中设置 DOUYIN_COOKIE=你的Cookie值，然后重启服务。\n\n获取方式：浏览器登录 douyin.com → F12 → Application → Cookies → 复制所有 cookie 值。"
        }

    print(f"[ranking {time.strftime('%H:%M:%S')}] 搜索爆款视频...")
    seen_ids: set[str] = set()
    all_videos: list[dict] = []

    # 按内容类关键词搜索热门视频
    for kw in _VIRAL_SEARCH_KEYWORDS:
        aweme_list = _search_videos(kw, count=15)
        for aweme in aweme_list:
            info = _extract_video_info(aweme, 0)
            if info and info["id"] not in seen_ids:
                seen_ids.add(info["id"])
                all_videos.append(info)
        time.sleep(0.3)
        if len(all_videos) >= 200:
            break

    if not all_videos:
        return {"videos": [], "error": "视频搜索未返回结果，请检查 Cookie 是否有效（可能已过期）。"}

    # 按爆款指数排序
    all_videos.sort(key=lambda v: _viral_score({
        "digg_count": v["digg_count"],
        "share_count": v["share_count"],
        "comment_count": v["comment_count"],
        "collect_count": v["collect_count"],
        "play_count": v["play_count"],
    }), reverse=True)

    # 取 Top 100，重新标排名
    all_videos = all_videos[:100]
    for i, v in enumerate(all_videos):
        v["rank"] = i + 1

    print(f"[ranking {time.strftime('%H:%M:%S')}] 爆款采集完成: {len(all_videos)} 条")
    return {"videos": all_videos, "error": None}


def _fetch_tiktok_trending() -> dict:
    """采集 TikTok 热门视频排行。返回 {"videos": [...], "error": str|None}"""
    # TikTok 的 trending API 需要复杂的认证（设备注册、X-Bogus 签名等），
    # 暂无法从后端直接调用。请配置 Cookie 后再试。
    return {"videos": [], "error": "TikTok 排行需要配置 Cookie 认证，请参考文档设置"}


# ═══════════════════════════════════════════════════════
# 公共接口
# ═══════════════════════════════════════════════════════

_FETCHERS = {
    "douyin": _fetch_douyin_viral,
    "tiktok": _fetch_tiktok_trending,
}


def get_ranking(platform: str, page: int = 1, page_size: int = 50) -> dict:
    """获取指定平台的排行数据（带缓存）。"""
    if platform not in _FETCHERS:
        return {"error": f"不支持的平台: {platform}", "videos": [], "total": 0}

    cache_age = _get_cache_age_seconds(platform)
    cache = _load_cache()

    # 缓存有效，直接返回
    if cache_age is not None and cache_age < RANKING_CACHE_TTL_SECONDS:
        videos = cache.get(platform, {}).get("videos", [])
        return _paginate(platform, videos, page, page_size,
                         cached_at=cache[platform]["updated_at"], is_stale=False)

    # 缓存过期但不至于太老：返回旧数据 + 后台异步刷新
    if cache_age is not None and cache_age < RANKING_CACHE_MAX_AGE_SECONDS:
        videos = cache.get(platform, {}).get("videos", [])
        # 异步刷新
        lock = _get_platform_lock(platform)
        if lock.acquire(blocking=False):
            t = threading.Thread(target=_refresh_cache, args=(platform,), daemon=True)
            t.start()
        return _paginate(platform, videos, page, page_size,
                         cached_at=cache[platform]["updated_at"], is_stale=True)

    # 无缓存或缓存太老：同步刷新
    result = _refresh_cache(platform)
    return _paginate(platform, result["videos"], page, page_size,
                     cached_at=datetime.now(timezone.utc).isoformat(), is_stale=False,
                     error=result.get("error"))


def _paginate(platform: str, videos: list, page: int, page_size: int,
              cached_at: str, is_stale: bool, error: str | None = None) -> dict:
    """分页结果。"""
    total = len(videos)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    response = {
        "platform": platform,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "videos": videos[start:end],
        "cached_at": cached_at,
        "is_stale": is_stale,
    }
    if error and not videos:
        response["error"] = error
    return response


def _refresh_cache(platform: str) -> dict:
    """同步刷新指定平台的缓存。"""
    lock = _get_platform_lock(platform)
    with lock:
        fetcher = _FETCHERS.get(platform)
        if not fetcher:
            return {"videos": [], "error": f"未知平台: {platform}"}

        print(f"[ranking {time.strftime('%H:%M:%S')}] 刷新 {platform} 排行...")
        result = fetcher()
        error = result.get("error")
        videos = result.get("videos", [])

        if videos or error:
            cache = _load_cache()
            cache[platform] = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "videos": videos,
                "error": error,
            }
            _save_cache(cache)
            print(f"[ranking {time.strftime('%H:%M:%S')}] {platform} 刷新完成: {len(videos)} 条, error={'yes' if error else 'no'}")
        return result


def force_refresh(platform: str) -> dict:
    """强制同步刷新（用户手动触发）。"""
    if platform not in _FETCHERS:
        return {"error": f"不支持的平台: {platform}"}
    result = _refresh_cache(platform)
    return {
        "status": "done",
        "count": len(result.get("videos", [])),
        "error": result.get("error"),
    }


# ═══════════════════════════════════════════════════════
# 批量下载队列
# ═══════════════════════════════════════════════════════

def batch_download(platform: str, video_ids: list[str], auto_analyze: bool = False) -> dict:
    """将一批视频加入下载队列。"""
    cache = _load_cache()
    plat_cache = cache.get(platform, {})
    all_videos = {v["id"]: v for v in plat_cache.get("videos", [])}

    items = []
    queued_count = 0
    skipped_count = 0
    failed_count = 0

    # 检查哪些已经在视频库中
    lib = load_library()
    lib_ids = {v.get("id", "") for v in lib.get("videos", [])}

    for vid in video_ids:
        if vid in lib_ids:
            skipped_count += 1
            items.append({"video_id": vid, "status": "skipped", "share_url": ""})
        elif vid in all_videos:
            queued_count += 1
            items.append({"video_id": vid, "status": "queued", "share_url": all_videos[vid].get("share_url", "")})
        else:
            failed_count += 1
            items.append({"video_id": vid, "status": "failed", "share_url": ""})

    if queued_count == 0:
        return {
            "status": "done",
            "queued_count": 0,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "items": items,
        }

    # 初始化队列
    queue_key = platform
    with _batch_lock:
        _batch_queues[queue_key] = {
            "total": queued_count,
            "completed": 0,
            "downloading": 0,
            "failed": 0,
            "items": items,
            "updated_at": time.time(),
        }

    # 后台启动下载
    preview_items = [i for i in items if i["status"] == "queued"]
    t = threading.Thread(target=_execute_batch_download, args=(platform, preview_items), daemon=True)
    t.start()

    return {
        "status": "queued",
        "queued_count": queued_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "items": items,
    }


def _execute_batch_download(platform: str, items: list[dict]):
    """在后台线程中顺序执行批量下载。"""
    import sys
    import subprocess
    import os
    import re
    import shutil

    queue_key = platform
    completed = 0
    failed = 0

    for item in items:
        vid = item["video_id"]
        url = item.get("share_url", "")
        if not url:
            continue

        # 更新队列状态
        with _batch_lock:
            if queue_key in _batch_queues:
                _batch_queues[queue_key]["downloading"] = 1
                _batch_queues[queue_key]["current"] = {"video_id": vid, "progress": 0}
                _batch_queues[queue_key]["updated_at"] = time.time()

        try:
            video_dir = VIDEOS_DIR / vid
            video_dir.mkdir(parents=True, exist_ok=True)

            vdl_path = SCRIPTS_DIR / "vdl.py"
            if not vdl_path.exists():
                raise FileNotFoundError(f"下载脚本不存在: {vdl_path}")

            process = subprocess.run(
                [sys.executable, str(vdl_path), url, "-o", str(video_dir)],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=600,
                cwd=str(SCRIPTS_DIR.parent),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )

            if process.returncode != 0:
                raise RuntimeError(process.stderr[-300:] or process.stdout[-300:] or "下载失败")

            # 展平文件
            all_mp4 = list(video_dir.rglob("*.mp4"))
            if all_mp4 and all_mp4[0].parent != video_dir:
                shutil.move(str(all_mp4[0]), str(video_dir / all_mp4[0].name))

            # 记录到 library
            lib = load_library()
            entry = find_video(lib, vid)
            if not entry:
                mp4_files = list(video_dir.glob("*.mp4"))
                size_mb = 0
                title = ""
                if mp4_files:
                    size_mb = round(mp4_files[0].stat().st_size / 1024 / 1024, 1)
                    title = mp4_files[0].stem[:100]

                lib["videos"].append({
                    "id": vid,
                    "url": url,
                    "title": title or vid,
                    "platform": platform,
                    "file_size_mb": size_mb,
                    "download_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "transcript_status": "pending",
                    "analysis_status": "pending",
                    "deepseek_status": "pending",
                    "tags": [],
                    "viral_score": 0,
                    "metrics": {},
                    "script_stats": {},
                    "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                })
                save_library(lib)

            item["status"] = "downloaded"
            completed += 1

        except Exception as e:
            item["status"] = "failed"
            item["error"] = str(e)
            failed += 1

        with _batch_lock:
            if queue_key in _batch_queues:
                _batch_queues[queue_key]["completed"] = completed
                _batch_queues[queue_key]["failed"] = failed
                _batch_queues[queue_key]["downloading"] = 0
                _batch_queues[queue_key]["updated_at"] = time.time()

        # 避免被限流
        time.sleep(2)


def get_batch_progress(platform: str) -> dict:
    """获取批量下载进度。"""
    with _batch_lock:
        q = _batch_queues.get(platform)
        if not q:
            return {"total": 0, "completed": 0, "downloading": 0, "failed": 0, "finished": True}
        finished = q["completed"] + q.get("failed", 0) >= q["total"]
        return {
            "total": q["total"],
            "completed": q["completed"],
            "downloading": q.get("downloading", 0),
            "failed": q.get("failed", 0),
            "finished": finished,
            "current": q.get("current"),
        }
