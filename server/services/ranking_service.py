"""
排行榜服务：排行数据采集 + 缓存 + 批量下载队列。
"""
import json
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
# 排行采集核心
# ═══════════════════════════════════════════════════════

def _fetch_douyin_hot() -> dict:
    """采集抖音热榜数据。返回 {"videos": [...], "error": str|None}"""
    try:
        import urllib.request
        import urllib.parse

        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        params = {
            "detail_list": "1",
            "source": "6",
            "board_type": "0",
            "board_sub_type": "",
            "version_code": "170400",
            "version_name": "17.4.0",
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
        }
        full_url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/discover",
            "Accept": "application/json, text/plain, */*",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        word_list = data.get("data", {}).get("word_list", [])
        if not word_list:
            return {"videos": [], "error": "抖音热榜 API 返回数据为空（可能需要 Cookie 认证）"}

        videos = []
        for idx, item in enumerate(word_list[:100]):
            hot_value = item.get("hot_value", 0)
            word = item.get("word", "")
            aweme_infos = item.get("aweme_infos") or []
            # 取第一个关联视频的信息
            if aweme_infos:
                aweme = aweme_infos[0].get("aweme_info", {})
                video_id = str(aweme.get("aweme_id", ""))
                title = aweme.get("desc", word)[:200]
                author_info = aweme.get("author", {})
                author = author_info.get("nickname", "") if author_info else ""
                duration = aweme.get("duration", 0) // 1000 if aweme.get("duration") else 0
                cover_url = ""
                video_cover = aweme.get("video", {}).get("cover", {})
                if video_cover:
                    url_list = video_cover.get("url_list", [])
                    cover_url = url_list[0] if url_list else ""
                stats = aweme.get("statistics", {})
                play_count = stats.get("play_count", hot_value)
                share_url = aweme.get("share_url", "") or f"https://www.douyin.com/video/{video_id}"
                tags = [t.get("tag_name", "") for t in aweme.get("text_extra", []) if t.get("tag_name")]
            else:
                video_id = f"hot_{idx}_{int(time.time())}"
                title = word[:200]
                author = ""
                duration = 0
                cover_url = ""
                play_count = hot_value
                share_url = f"https://www.douyin.com/search/{urllib.parse.quote(word)}"
                tags = []

            # 过滤 <=60s
            if duration > 0 and duration > 60:
                continue

            videos.append({
                "id": video_id,
                "rank": idx + 1,
                "title": title or word,
                "author": author or "未知作者",
                "play_count": play_count or hot_value,
                "duration_sec": duration,
                "cover_url": cover_url,
                "tags": tags[:5],
                "platform": "douyin",
                "share_url": share_url,
            })

        # 按播放量降序
        videos.sort(key=lambda v: v["play_count"], reverse=True)
        for i, v in enumerate(videos):
            v["rank"] = i + 1

        return {"videos": videos, "error": None}
    except Exception as e:
        return {"videos": [], "error": f"抖音 API 请求失败: {str(e)}"}


def _fetch_tiktok_trending() -> dict:
    """采集 TikTok 热门视频排行。返回 {"videos": [...], "error": str|None}"""
    # TikTok 的 trending API 需要复杂的认证（设备注册、X-Bogus 签名等），
    # 暂无法从后端直接调用。请配置 Cookie 后再试。
    return {"videos": [], "error": "TikTok 排行需要配置 Cookie 认证，请参考文档设置"}


# ═══════════════════════════════════════════════════════
# 公共接口
# ═══════════════════════════════════════════════════════

_FETCHERS = {
    "douyin": _fetch_douyin_hot,
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
