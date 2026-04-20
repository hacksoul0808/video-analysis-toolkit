#!/usr/bin/env python3
"""
抖音视频下载工具 - 通过 iesdouyin 分享页提取视频链接

用法:
  # 下载单个视频（支持分享短链接和完整链接）
  python3 download_douyin.py "https://v.douyin.com/AEVS7UB1-II/"
  python3 download_douyin.py "https://www.douyin.com/video/7628940941864324394"

  # 下载无水印版本（默认）
  python3 download_douyin.py --no-watermark "https://v.douyin.com/xxx/"

  # 下载有水印版本
  python3 download_douyin.py --watermark "https://v.douyin.com/xxx/"

原理:
  1. 解析短链接获取视频 ID
  2. 访问 iesdouyin.com 分享页获取 video_id
  3. 通过 aweme.snssdk.com/aweme/v1/play/ 下载无水印视频
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

OUTPUT_DIR = Path(__file__).parent / "videos"


def get_session():
    from curl_cffi import requests as cf_requests
    return cf_requests.Session(impersonate="chrome120")


def resolve_share_url(session, url):
    """解析分享短链接，获取视频 ID"""
    print(f"解析链接: {url}")
    resp = session.get(url, timeout=15, allow_redirects=True)
    final_url = str(resp.url)
    print(f"最终地址: {final_url}")

    # 提取视频 ID
    m = re.search(r'/video/(\d+)', final_url)
    if m:
        return m.group(1)

    # 从 redirect 的 location 提取
    m = re.search(r'video/(\d+)', final_url)
    if m:
        return m.group(1)

    return None


def get_video_internal_id(session, video_id):
    """通过 iesdouyin 分享页获取视频内部 ID (video_id for CDN)"""
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    print(f"获取视频信息: {share_url}")

    resp = session.get(share_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    })

    if resp.status_code != 200:
        print(f"请求失败: {resp.status_code}")
        return None, None

    # 提取 video_id 和标题
    # Pattern: play_addr with video_id
    m = re.search(r'video_id=([a-zA-Z0-9_]+)', resp.text)
    internal_id = m.group(1) if m else None

    # 提取标题
    title = None
    m = re.search(r'"desc"\s*:\s*"([^"]*)"', resp.text)
    if m:
        title = m.group(1).encode().decode('unicode_escape') if '\\u' in m.group(1) else m.group(1)

    # 也尝试从 _ROUTER_DATA 提取更多信息
    router_match = re.search(r'window\._ROUTER_DATA\s*=\s*({.*?});\s*</script>', resp.text, re.DOTALL)
    if router_match:
        try:
            data = json.loads(router_match.group(1))
            loader = data.get("loaderData", {})
            for k, v in loader.items():
                if isinstance(v, dict):
                    desc = v.get("desc")
                    if desc and not title:
                        title = desc
        except:
            pass

    if not title:
        m = re.search(r'<title>([^<]+)</title>', resp.text)
        title = m.group(1) if m else f"douyin_{video_id}"

    print(f"视频标题: {title}")
    print(f"内部 ID: {internal_id}")
    return internal_id, title


def download_video(session, internal_id, video_id, title, watermark=False):
    """下载视频"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    endpoint = "playwm" if watermark else "play"
    url = f"https://aweme.snssdk.com/aweme/v1/{endpoint}/?video_id={internal_id}&ratio=720p&line=0"

    # 清理文件名
    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)[:50].strip('_')
    wm_tag = "_wm" if watermark else ""
    filename = f"{safe_title}_{video_id}{wm_tag}.mp4"
    filepath = OUTPUT_DIR / filename

    print(f"\n下载{'有水印' if watermark else '无水印'}视频...")
    print(f"URL: {url[:100]}...")

    resp = session.get(url, timeout=120, allow_redirects=True)

    if resp.status_code != 200:
        print(f"下载失败: HTTP {resp.status_code}")
        return None

    content_type = resp.headers.get('content-type', '')
    if 'video' not in content_type:
        print(f"返回的不是视频: {content_type}")
        print(f"内容: {resp.text[:200]}")
        return None

    with open(filepath, "wb") as f:
        f.write(resp.content)

    size_mb = len(resp.content) / 1024 / 1024
    print(f"下载完成: {filepath} ({size_mb:.1f} MB)")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="抖音视频下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "https://v.douyin.com/AEVS7UB1-II/"
  %(prog)s "https://www.douyin.com/video/7628940941864324394"
  %(prog)s --watermark "https://v.douyin.com/xxx/"
        """
    )
    parser.add_argument("url", help="抖音视频链接（短链接或完整链接）")
    parser.add_argument("--watermark", action="store_true", help="下载有水印版本")
    parser.add_argument("--no-watermark", action="store_true", default=True, help="下载无水印版本（默认）")
    args = parser.parse_args()

    session = get_session()

    # Step 1: 解析链接获取视频 ID
    url = args.url.strip()
    video_id = None

    # 直接是 video ID
    m = re.search(r'/video/(\d+)', url)
    if m:
        video_id = m.group(1)
    else:
        # 短链接，需要解析
        video_id = resolve_share_url(session, url)

    if not video_id:
        print("无法获取视频 ID，请检查链接是否正确")
        sys.exit(1)

    print(f"视频 ID: {video_id}")

    # Step 2: 获取视频内部 ID
    internal_id, title = get_video_internal_id(session, video_id)
    if not internal_id:
        print("无法获取视频下载信息")
        sys.exit(1)

    # Step 3: 下载
    filepath = download_video(session, internal_id, video_id, title, watermark=args.watermark)

    if filepath:
        print(f"\n✓ 下载成功: {filepath}")
    else:
        print("\n✗ 下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
