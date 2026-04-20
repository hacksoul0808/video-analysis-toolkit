#!/usr/bin/env python3
"""
vdl - 通用视频下载工具

自动识别平台，选择最佳下载方式。

支持平台:
  - 抖音 (Douyin) - 内置解析器，无水印下载
  - YouTube - yt-dlp
  - Bilibili - yt-dlp / lux
  - TikTok - yt-dlp
  - Twitter/X - yt-dlp / cobalt
  - Instagram - yt-dlp
  - 小红书 (Xiaohongshu) - lux
  - 快手 (Kuaishou) - lux
  - 微博 (Weibo) - lux
  - 其他 1900+ 站点 - yt-dlp

用法:
  python3 vdl.py "https://v.douyin.com/xxx/"
  python3 vdl.py "https://www.youtube.com/watch?v=xxx"
  python3 vdl.py "https://www.bilibili.com/video/BVxxx"
  python3 vdl.py "https://x.com/user/status/xxx"

  # 指定引擎
  python3 vdl.py --engine yt-dlp "URL"
  python3 vdl.py --engine lux "URL"

  # 列出可用格式
  python3 vdl.py --list-formats "URL"

  # 指定输出目录
  python3 vdl.py -o ~/Videos "URL"
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).parent / "videos"


def detect_platform(url):
    """检测视频平台"""
    patterns = {
        "douyin": r"(douyin\.com|iesdouyin\.com)",
        "youtube": r"(youtube\.com|youtu\.be)",
        "bilibili": r"bilibili\.com",
        "tiktok": r"tiktok\.com",
        "twitter": r"(twitter\.com|x\.com|t\.co)",
        "instagram": r"instagram\.com",
        "xiaohongshu": r"(xiaohongshu\.com|xhslink\.com)",
        "kuaishou": r"(kuaishou\.com|gifshow\.com)",
        "weibo": r"weibo\.(com|cn)",
    }
    for platform, pattern in patterns.items():
        if re.search(pattern, url, re.I):
            return platform
    return "unknown"


def choose_engine(platform):
    """根据平台选择最佳引擎"""
    engine_preference = {
        "douyin": ["builtin", "lux", "yt-dlp"],
        "youtube": ["yt-dlp"],
        "bilibili": ["yt-dlp", "lux"],
        "tiktok": ["yt-dlp"],
        "twitter": ["yt-dlp", "gallery-dl"],
        "instagram": ["yt-dlp", "gallery-dl"],
        "xiaohongshu": ["lux", "yt-dlp"],
        "kuaishou": ["lux", "yt-dlp"],
        "weibo": ["lux", "yt-dlp"],
        "unknown": ["yt-dlp", "lux"],
    }

    available = {
        "yt-dlp": shutil.which("yt-dlp") is not None,
        "lux": shutil.which("lux") is not None,
        "gallery-dl": shutil.which("gallery-dl") is not None,
        "you-get": shutil.which("you-get") is not None,
        "builtin": True,
    }

    preferences = engine_preference.get(platform, engine_preference["unknown"])
    for engine in preferences:
        if available.get(engine):
            return engine

    return None


def download_douyin_builtin(url, output_dir):
    """内置抖音下载器（无水印）"""
    from curl_cffi import requests as cf_requests
    import json

    session = cf_requests.Session(impersonate="chrome120")

    # 解析链接获取视频 ID
    video_id = None
    m = re.search(r'/video/(\d+)', url)
    if m:
        video_id = m.group(1)
    else:
        resp = session.get(url, timeout=15, allow_redirects=True)
        final_url = str(resp.url)
        m = re.search(r'/video/(\d+)', final_url)
        if m:
            video_id = m.group(1)

    if not video_id:
        print("无法从链接中提取视频 ID")
        return False

    # 获取视频信息
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    resp = session.get(share_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    })

    m = re.search(r'video_id=([a-zA-Z0-9_]+)', resp.text)
    if not m:
        print("无法提取视频内部 ID")
        return False
    internal_id = m.group(1)

    # 获取标题
    title = f"douyin_{video_id}"
    m = re.search(r'"desc"\s*:\s*"([^"]*)"', resp.text)
    if m:
        t = m.group(1)
        title = t.encode().decode('unicode_escape') if '\\u' in t else t

    # 下载无水印视频
    play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={internal_id}&ratio=720p&line=0"
    print(f"标题: {title[:60]}")
    print(f"下载无水印视频...")

    resp = session.get(play_url, timeout=120, allow_redirects=True)
    if resp.status_code != 200 or 'video' not in resp.headers.get('content-type', ''):
        print(f"下载失败: {resp.status_code}")
        return False

    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)[:50].strip('_')
    filename = f"{safe_title}_{video_id}.mp4"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        f.write(resp.content)

    size_mb = len(resp.content) / 1024 / 1024
    print(f"下载完成: {filepath} ({size_mb:.1f} MB)")
    return True


def download_ytdlp(url, output_dir, list_formats=False):
    """使用 yt-dlp 下载"""
    cmd = ["yt-dlp"]

    if list_formats:
        cmd += ["-F", url]
        subprocess.run(cmd)
        return True

    cmd += [
        "-o", str(output_dir / "%(title).50s_%(id)s.%(ext)s"),
        "--no-check-certificates",
        "--merge-output-format", "mp4",
        url,
    ]

    print(f"执行: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_lux(url, output_dir, list_formats=False):
    """使用 lux 下载"""
    cmd = ["lux"]

    if list_formats:
        cmd += ["-i", url]
        subprocess.run(cmd)
        return True

    cmd += ["-o", str(output_dir), url]
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_gallerydl(url, output_dir):
    """使用 gallery-dl 下载"""
    cmd = [
        "gallery-dl",
        "-d", str(output_dir),
        url,
    ]
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_youget(url, output_dir):
    """使用 you-get 下载"""
    cmd = ["you-get", "-o", str(output_dir), url]
    print(f"执行: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="vdl - 通用视频下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="视频链接")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="输出目录")
    parser.add_argument("-e", "--engine", choices=["yt-dlp", "lux", "gallery-dl", "you-get", "builtin"],
                        help="指定下载引擎")
    parser.add_argument("-F", "--list-formats", action="store_true", help="列出可用格式")
    parser.add_argument("--info", action="store_true", help="只显示信息，不下载")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = args.url.strip()
    platform = detect_platform(url)
    engine = args.engine or choose_engine(platform)

    print(f"平台: {platform}")
    print(f"引擎: {engine}")
    print(f"输出: {output_dir}")
    print()

    if not engine:
        print("没有找到可用的下载引擎！请安装 yt-dlp:")
        print("  pip install yt-dlp")
        sys.exit(1)

    # 列出格式
    if args.list_formats:
        if engine in ("yt-dlp", "lux"):
            download_ytdlp(url, output_dir, list_formats=True) if engine == "yt-dlp" else download_lux(url, output_dir, list_formats=True)
        else:
            print("此引擎不支持列出格式")
        return

    # 下载
    success = False
    if engine == "builtin":
        success = download_douyin_builtin(url, output_dir)
    elif engine == "yt-dlp":
        success = download_ytdlp(url, output_dir)
    elif engine == "lux":
        success = download_lux(url, output_dir)
    elif engine == "gallery-dl":
        success = download_gallerydl(url, output_dir)
    elif engine == "you-get":
        success = download_youget(url, output_dir)

    if not success and engine != "yt-dlp":
        print(f"\n{engine} 下载失败，尝试 yt-dlp 兜底...")
        success = download_ytdlp(url, output_dir)

    if success:
        print("\n✓ 下载完成！")
    else:
        print("\n✗ 下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
