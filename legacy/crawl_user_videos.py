#!/usr/bin/env python3
"""
抖音用户视频批量爬取下载工具

给一个用户主页链接，自动爬取所有视频并下载（无水印）。

原理:
  1. 解析分享链接 → 获取 sec_uid
  2. 通过 Crawl4AI 爬取 iesdouyin 分享页
  3. 通过 Playwright 拦截 API 请求获取视频列表（备用）
  4. 通过 iesdouyin 分享页逐个提取 video_id
  5. 通过 aweme.snssdk.com 下载无水印视频

用法:
  # 从用户主页分享链接下载
  python3 crawl_user_videos.py "https://v.douyin.com/aHOMe6-ryPw/"

  # 从 sec_uid 下载
  python3 crawl_user_videos.py --sec-uid "MS4wLjABAAAAxxx"

  # 限制下载数量
  python3 crawl_user_videos.py --max 5 "https://v.douyin.com/aHOMe6-ryPw/"

  # 只列出不下载
  python3 crawl_user_videos.py --list-only "https://v.douyin.com/aHOMe6-ryPw/"
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

OUTPUT_DIR = Path(__file__).parent / "videos"


@dataclass
class VideoInfo:
    video_id: str
    internal_id: str = ""
    title: str = ""
    cover_url: str = ""
    download_url: str = ""
    downloaded: bool = False
    file_path: str = ""
    file_size_mb: float = 0


def get_session():
    from curl_cffi import requests as cf_requests
    return cf_requests.Session(impersonate="chrome120")


def resolve_user_share_url(session, url):
    """解析用户分享短链接 → sec_uid"""
    print(f"[1/4] 解析分享链接: {url}")
    resp = session.get(url, timeout=15, allow_redirects=True)
    final_url = str(resp.url)
    print(f"  → {final_url[:80]}...")

    # 提取 sec_uid
    m = re.search(r'sec_uid=([^&]+)', final_url) or re.search(r'/user/([^?&/]+)', final_url)
    if m:
        sec_uid = m.group(1)
        print(f"  sec_uid: {sec_uid}")
        return sec_uid

    print("  ✗ 无法提取 sec_uid")
    return None


def get_user_video_ids_via_playwright(sec_uid, max_scroll=10):
    """
    通过 Playwright 渲染 iesdouyin 用户分享页 + 拦截 API 获取视频列表。
    这是最可靠的方式：iesdouyin 的移动分享页会调用 /aweme/post API，
    Playwright 拦截这些请求就能拿到完整的视频数据。
    """
    from playwright.sync_api import sync_playwright

    all_videos = []  # List of (video_id, title) tuples
    seen_ids = set()

    def on_response(response):
        url = response.url
        if 'aweme' in url and '/post' in url and response.status == 200:
            try:
                data = response.json()
                for v in data.get('aweme_list', []):
                    vid = v.get('aweme_id')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        desc = v.get('desc', '')
                        all_videos.append((vid, desc))
            except:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            viewport={"width": 390, "height": 844},
        )
        page.on("response", on_response)

        url = f"https://www.iesdouyin.com/share/user/{sec_uid}"
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"  页面加载: {e}")

        import time as _time
        _time.sleep(5)

        title = page.title()
        print(f"  用户页标题: {title}")
        print(f"  首次加载: {len(all_videos)} 个视频")

        # Scroll to trigger loading more videos
        prev_count = len(all_videos)
        for i in range(max_scroll):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            _time.sleep(2)
            if len(all_videos) > prev_count:
                print(f"  滚动 {i+1}: 新增 {len(all_videos) - prev_count} 个，总计 {len(all_videos)}")
                prev_count = len(all_videos)
            else:
                # No new videos loaded, might be at the end
                if i > 1:
                    break

        browser.close()

    return all_videos


def get_user_video_ids_via_web(session, sec_uid, max_pages=10):
    """
    获取用户视频列表。
    优先使用 Playwright（最可靠），失败则回退到静态解析。
    """
    print(f"\n[2/4] 获取用户视频列表...")

    # 方法 1: Playwright 渲染 + API 拦截（最可靠）
    try:
        print("  使用 Playwright 渲染用户页...")
        videos = get_user_video_ids_via_playwright(sec_uid)
        if videos:
            video_ids = [v[0] for v in videos]
            # 缓存标题信息
            global _video_titles
            _video_titles = {v[0]: v[1] for v in videos}
            print(f"  ✓ Playwright 成功获取 {len(video_ids)} 个视频")
            return video_ids
        else:
            print("  Playwright 未获取到视频，尝试备用方案...")
    except Exception as e:
        print(f"  Playwright 失败 ({e})，尝试备用方案...")

    # 方法 2: iesdouyin 静态页面解析
    user_url = f"https://www.iesdouyin.com/share/user/{sec_uid}"
    resp = session.get(user_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    })

    video_ids = []

    # 从 _ROUTER_DATA 提取
    router_match = re.search(r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>', resp.text, re.DOTALL)
    if router_match:
        try:
            data = json.loads(router_match.group(1))
            def find_aweme_ids(obj):
                ids = []
                if isinstance(obj, dict):
                    if 'aweme_id' in obj:
                        ids.append(obj['aweme_id'])
                    for v in obj.values():
                        ids.extend(find_aweme_ids(v))
                elif isinstance(obj, list):
                    for item in obj:
                        ids.extend(find_aweme_ids(item))
                return ids

            video_ids = find_aweme_ids(data)
            print(f"  从 _ROUTER_DATA 提取到 {len(video_ids)} 个视频 ID")
        except Exception as e:
            print(f"  _ROUTER_DATA 解析失败: {e}")

    # 从 HTML 中直接搜索视频链接
    if not video_ids:
        ids_in_html = re.findall(r'/video/(\d{15,25})', resp.text)
        video_ids = list(dict.fromkeys(ids_in_html))
        print(f"  从 HTML 链接提取到 {len(video_ids)} 个视频 ID")

    video_ids = list(dict.fromkeys(video_ids))
    print(f"  总计: {len(video_ids)} 个唯一视频 ID")
    return video_ids


# Global cache for video titles from Playwright
_video_titles = {}


def get_video_info(session, video_id):
    """获取单个视频的详细信息（internal_id + 标题）"""
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    try:
        resp = session.get(share_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        })
    except Exception as e:
        return None

    if resp.status_code != 200:
        return None

    # 提取 internal video_id
    m = re.search(r'video_id=([a-zA-Z0-9_]+)', resp.text)
    internal_id = m.group(1) if m else None

    # 提取标题 (优先使用 Playwright 缓存)
    title = _video_titles.get(video_id, "")
    if not title:
        m = re.search(r'"desc"\s*:\s*"([^"]*)"', resp.text)
        if m:
            t = m.group(1)
            title = t.encode().decode('unicode_escape') if '\\u' in t else t
    if not title:
        m = re.search(r'<title>([^<]+)</title>', resp.text)
        title = m.group(1) if m else f"douyin_{video_id}"

    # 提取封面
    cover_url = ""
    m = re.search(r'"cover"\s*:\s*\{[^}]*"url_list"\s*:\s*\["([^"]+)"', resp.text)
    if m:
        cover_url = m.group(1)

    if internal_id:
        return VideoInfo(
            video_id=video_id,
            internal_id=internal_id,
            title=title,
            cover_url=cover_url,
        )
    return None


def download_video(session, video: VideoInfo, output_dir: Path):
    """下载单个视频"""
    play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video.internal_id}&ratio=720p&line=0"

    try:
        resp = session.get(play_url, timeout=120, allow_redirects=True)
    except Exception as e:
        print(f"    ✗ 下载失败: {e}")
        return False

    if resp.status_code != 200:
        print(f"    ✗ HTTP {resp.status_code}")
        return False

    content_type = resp.headers.get('content-type', '')
    if 'video' not in content_type:
        print(f"    ✗ 非视频内容: {content_type}")
        return False

    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', video.title)[:50].strip('_')
    filename = f"{safe_title}_{video.video_id}.mp4"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        f.write(resp.content)

    size_mb = len(resp.content) / 1024 / 1024
    video.downloaded = True
    video.file_path = str(filepath)
    video.file_size_mb = round(size_mb, 1)
    return True


def run(url=None, sec_uid=None, max_videos=50, list_only=False, output_dir=None):
    output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    session = get_session()

    # Step 1: 获取 sec_uid
    if not sec_uid and url:
        sec_uid = resolve_user_share_url(session, url)
    if not sec_uid:
        print("错误: 无法获取 sec_uid")
        return

    # Step 2: 获取视频列表
    video_ids = get_user_video_ids_via_web(session, sec_uid)
    if not video_ids:
        print("未找到任何视频")
        return

    video_ids = video_ids[:max_videos]

    # Step 3: 获取每个视频的详细信息
    print(f"\n[3/4] 获取 {len(video_ids)} 个视频的详细信息...")
    videos = []
    for i, vid in enumerate(video_ids):
        info = get_video_info(session, vid)
        if info:
            videos.append(info)
            print(f"  [{i+1}/{len(video_ids)}] {info.title[:50]}...")
        else:
            print(f"  [{i+1}/{len(video_ids)}] {vid} - 获取失败")
        time.sleep(0.5)  # rate limiting

    print(f"  成功获取 {len(videos)}/{len(video_ids)} 个视频信息")

    if list_only:
        print(f"\n视频列表:")
        for i, v in enumerate(videos, 1):
            print(f"  {i}. [{v.video_id}] {v.title[:60]}")
        # Save list
        list_file = output_dir.parent / "video_list.json"
        with open(list_file, "w") as f:
            json.dump([asdict(v) for v in videos], f, ensure_ascii=False, indent=2)
        print(f"\n列表已保存: {list_file}")
        return

    # Step 4: 下载
    print(f"\n[4/4] 开始下载 {len(videos)} 个视频...")
    t0 = time.time()
    success_count = 0
    total_size = 0

    for i, video in enumerate(videos):
        print(f"  [{i+1}/{len(videos)}] {video.title[:50]}...")
        ok = download_video(session, video, output_dir)
        if ok:
            success_count += 1
            total_size += video.file_size_mb
            print(f"    ✓ {video.file_size_mb} MB")
        time.sleep(1)  # rate limiting

    elapsed = time.time() - t0

    # Summary
    print(f"\n{'='*60}")
    print(f"下载完成!")
    print(f"  成功: {success_count}/{len(videos)}")
    print(f"  总大小: {total_size:.1f} MB")
    print(f"  总耗时: {elapsed:.1f}s")
    print(f"  平均速度: {total_size/elapsed:.1f} MB/s" if elapsed > 0 else "")
    print(f"  保存目录: {output_dir}")

    # Save manifest
    manifest = {
        "sec_uid": sec_uid,
        "download_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_videos": len(videos),
        "success": success_count,
        "total_size_mb": round(total_size, 1),
        "elapsed_sec": round(elapsed, 1),
        "videos": [asdict(v) for v in videos],
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  清单: {manifest_file}")


def main():
    parser = argparse.ArgumentParser(description="抖音用户视频批量爬取下载")
    parser.add_argument("url", nargs="?", help="用户主页分享链接")
    parser.add_argument("--sec-uid", help="用户 sec_uid")
    parser.add_argument("--max", type=int, default=50, help="最多下载数量 (默认 50)")
    parser.add_argument("--list-only", action="store_true", help="只列出视频，不下载")
    parser.add_argument("-o", "--output", help="输出目录")
    args = parser.parse_args()

    if not args.url and not args.sec_uid:
        parser.print_help()
        return

    run(
        url=args.url,
        sec_uid=args.sec_uid,
        max_videos=args.max,
        list_only=args.list_only,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
