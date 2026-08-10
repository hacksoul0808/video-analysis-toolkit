#!/usr/bin/env python3
"""
Benchmark different video download approaches.
Tests: speed, reliability, watermark, quality.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, asdict

BENCH_DIR = Path(__file__).parent / "benchmark_results"
BENCH_DIR.mkdir(exist_ok=True)

# Test URLs - different platforms
TEST_CASES = {
    "douyin_builtin": {
        "url": "https://v.douyin.com/AEVS7UB1-II/",
        "platform": "douyin",
        "engine": "builtin",
    },
    "douyin_ytdlp": {
        "url": "https://www.douyin.com/video/7628940941864324394",
        "platform": "douyin",
        "engine": "yt-dlp",
    },
    "douyin_lux": {
        "url": "https://www.douyin.com/video/7628940941864324394",
        "platform": "douyin",
        "engine": "lux",
    },
}

@dataclass
class BenchResult:
    name: str
    engine: str
    platform: str
    url: str
    success: bool
    duration_sec: float
    file_size_mb: float
    speed_mbps: float  # megabytes per second
    resolution: str
    duration_video: str
    has_watermark: str  # yes/no/unknown
    error: str = ""


def get_video_info(filepath):
    """Get video metadata using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(filepath)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)

        # Get video stream info
        video_stream = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                video_stream = s
                break

        resolution = "unknown"
        if video_stream:
            w = video_stream.get("width", "?")
            h = video_stream.get("height", "?")
            resolution = f"{w}x{h}"

        duration = data.get("format", {}).get("duration", "0")
        duration_sec = float(duration)
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        duration_str = f"{mins}:{secs:02d}"

        bitrate = data.get("format", {}).get("bit_rate", "0")
        bitrate_kbps = int(bitrate) // 1000 if bitrate else 0

        return resolution, duration_str, bitrate_kbps
    except Exception as e:
        return "unknown", "unknown", 0


def bench_builtin(url, output_path):
    """Benchmark built-in douyin downloader"""
    from curl_cffi import requests as cf_requests

    session = cf_requests.Session(impersonate="chrome120")

    # Step 1: Resolve URL
    t0 = time.time()
    resp = session.get(url, timeout=15, allow_redirects=True)
    final_url = str(resp.url)
    m = re.search(r'/video/(\d+)', final_url)
    video_id = m.group(1) if m else None
    t_resolve = time.time() - t0

    if not video_id:
        return None, {"resolve": t_resolve}, "Failed to resolve URL"

    # Step 2: Get video info from iesdouyin
    t1 = time.time()
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
    resp = session.get(share_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    })
    m = re.search(r'video_id=([a-zA-Z0-9_]+)', resp.text)
    internal_id = m.group(1) if m else None
    t_extract = time.time() - t1

    if not internal_id:
        return None, {"resolve": t_resolve, "extract": t_extract}, "Failed to extract video_id"

    # Step 3: Download
    t2 = time.time()
    play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={internal_id}&ratio=720p&line=0"
    resp = session.get(play_url, timeout=120, allow_redirects=True)
    t_download = time.time() - t2

    if resp.status_code != 200:
        return None, {"resolve": t_resolve, "extract": t_extract, "download": t_download}, f"HTTP {resp.status_code}"

    with open(output_path, "wb") as f:
        f.write(resp.content)

    timings = {
        "resolve": round(t_resolve, 2),
        "extract": round(t_extract, 2),
        "download": round(t_download, 2),
        "total": round(t_resolve + t_extract + t_download, 2),
    }

    return output_path, timings, None


def bench_ytdlp(url, output_path):
    """Benchmark yt-dlp"""
    t0 = time.time()
    cmd = [
        "yt-dlp",
        "-o", str(output_path),
        "--no-check-certificates",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    duration = time.time() - t0

    if result.returncode != 0:
        return None, {"total": round(duration, 2)}, result.stderr[-500:]

    return output_path, {"total": round(duration, 2)}, None


def bench_lux(url, output_dir):
    """Benchmark lux"""
    t0 = time.time()
    cmd = [
        os.path.expanduser("~/.local/bin/lux"),
        "-o", str(output_dir),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    duration = time.time() - t0

    if result.returncode != 0:
        return None, {"total": round(duration, 2)}, result.stderr[-500:]

    # Find the downloaded file
    files = sorted(output_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    output_path = files[0] if files else None

    return output_path, {"total": round(duration, 2)}, None


def run_benchmark():
    results = []

    for name, case in TEST_CASES.items():
        print(f"\n{'='*60}")
        print(f"Test: {name}")
        print(f"  URL: {case['url'][:60]}...")
        print(f"  Engine: {case['engine']}")

        output_dir = BENCH_DIR / name
        output_dir.mkdir(exist_ok=True)

        # Clean previous results
        for f in output_dir.glob("*"):
            if f.is_file():
                f.unlink()

        output_path = output_dir / f"test_{name}.mp4"

        try:
            if case["engine"] == "builtin":
                filepath, timings, error = bench_builtin(case["url"], output_path)
            elif case["engine"] == "yt-dlp":
                filepath, timings, error = bench_ytdlp(case["url"], output_path)
            elif case["engine"] == "lux":
                filepath, timings, error = bench_lux(case["url"], output_dir)
            else:
                continue

            if error:
                print(f"  ERROR: {error[:200]}")
                results.append(BenchResult(
                    name=name, engine=case["engine"], platform=case["platform"],
                    url=case["url"], success=False, duration_sec=timings.get("total", 0),
                    file_size_mb=0, speed_mbps=0, resolution="N/A",
                    duration_video="N/A", has_watermark="N/A", error=str(error)[:200],
                ))
                continue

            # Get file info
            if filepath and Path(filepath).exists():
                size_bytes = Path(filepath).stat().st_size
                size_mb = size_bytes / (1024 * 1024)
                total_time = timings.get("total", timings.get("download", 1))
                speed = size_mb / total_time if total_time > 0 else 0

                resolution, vid_duration, bitrate = get_video_info(filepath)

                print(f"  Timings: {json.dumps(timings)}")
                print(f"  Size: {size_mb:.1f} MB")
                print(f"  Speed: {speed:.1f} MB/s")
                print(f"  Resolution: {resolution}")
                print(f"  Duration: {vid_duration}")
                print(f"  Bitrate: {bitrate} kbps")

                # Check watermark heuristic (builtin = no wm, others = likely wm for douyin)
                has_wm = "no" if case["engine"] == "builtin" else "possible"

                results.append(BenchResult(
                    name=name, engine=case["engine"], platform=case["platform"],
                    url=case["url"], success=True, duration_sec=total_time,
                    file_size_mb=round(size_mb, 1), speed_mbps=round(speed, 2),
                    resolution=resolution, duration_video=vid_duration,
                    has_watermark=has_wm,
                ))
            else:
                results.append(BenchResult(
                    name=name, engine=case["engine"], platform=case["platform"],
                    url=case["url"], success=False, duration_sec=timings.get("total", 0),
                    file_size_mb=0, speed_mbps=0, resolution="N/A",
                    duration_video="N/A", has_watermark="N/A", error="No output file",
                ))
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append(BenchResult(
                name=name, engine=case["engine"], platform=case["platform"],
                url=case["url"], success=False, duration_sec=0,
                file_size_mb=0, speed_mbps=0, resolution="N/A",
                duration_video="N/A", has_watermark="N/A", error=str(e)[:200],
            ))

    # Print summary
    print(f"\n\n{'='*80}")
    print("BENCHMARK RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"{'Name':<20} {'Engine':<10} {'OK?':<5} {'Time(s)':<8} {'Size(MB)':<10} {'Speed(MB/s)':<12} {'Res':<12} {'WM?':<5}")
    print("-" * 80)
    for r in results:
        ok = "✓" if r.success else "✗"
        print(f"{r.name:<20} {r.engine:<10} {ok:<5} {r.duration_sec:<8.1f} {r.file_size_mb:<10.1f} {r.speed_mbps:<12.2f} {r.resolution:<12} {r.has_watermark:<5}")
        if r.error:
            print(f"  Error: {r.error[:100]}")

    # Save results
    with open(BENCH_DIR / "results.json", "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {BENCH_DIR / 'results.json'}")


if __name__ == "__main__":
    run_benchmark()
