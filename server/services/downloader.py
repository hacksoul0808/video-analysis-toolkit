"""
视频下载服务：调用 scripts/vdl.py 子进程下载视频。
"""
import json
import os
import re
import sys
import time
import subprocess
import threading
from pathlib import Path
from server.config import BASE_DIR, SCRIPTS_DIR


# 全局进度存储（供 HTTP handler 轮询）
progress_store: dict[str, dict] = {}


def download_video(url: str, output_dir: Path, video_id: str) -> dict:
    """下载视频到指定目录，返回元数据 dict。实时报告进度到 progress_store。"""
    print(f"[downloader {time.strftime('%H:%M:%S')}] 开始: {video_id} ← {url[:80]}")
    t0 = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    before = set(f.name for f in output_dir.glob("*.mp4") if f.is_file())
    vdl_path = SCRIPTS_DIR / "vdl.py"
    progress_store[video_id] = {"percent": 0, "status": "downloading"}

    process = subprocess.Popen(
        [sys.executable, str(vdl_path), url, "-o", str(output_dir)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace", bufsize=1, cwd=str(BASE_DIR),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )

    stdout_lines: list[str] = []

    def reader():
        for line in iter(process.stdout.readline, ''):
            line_stripped = line.strip()
            stdout_lines.append(line_stripped)
            if line_stripped:
                print(f"  [vdl] {line_stripped}", flush=True)
            m = re.search(r'PROGRESS:(\d+)', line_stripped)
            if m:
                progress_store[video_id] = {"percent": int(m.group(1)), "status": "downloading"}
            m2 = re.search(r'\[download\]\s+(\d+\.?\d*)%', line_stripped)
            if m2:
                progress_store[video_id] = {"percent": int(float(m2.group(1))), "status": "downloading"}

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    try:
        process.wait(timeout=600)
    except subprocess.TimeoutExpired:
        process.kill()
        progress_store[video_id] = {"percent": 100, "status": "error", "error": "下载超时 (10分钟)"}
        raise RuntimeError("下载超时: 超过 10 分钟")

    t.join(timeout=3)

    elapsed = time.time() - t0
    stdout_full = "\n".join(stdout_lines)

    if process.returncode != 0:
        print(f"[downloader {time.strftime('%H:%M:%S')}] 失败, rc={process.returncode}, 耗时 {elapsed:.1f}s")
        progress_store[video_id] = {"percent": 100, "status": "error", "error": stdout_full[-500:]}
        err_lines = stdout_lines[-5:] if stdout_lines else ["Unknown error"]
        raise RuntimeError("下载失败:\n" + "\n".join(err_lines))

    print(f"[downloader {time.strftime('%H:%M:%S')}] 完成, 耗时 {elapsed:.1f}s")
    progress_store[video_id] = {"percent": 100, "status": "done"}

    # 找到新下载的 mp4 文件
    after = set(f.name for f in output_dir.glob("*.mp4") if f.is_file())
    new_files = after - before

    if not new_files:
        err_lines = stdout_lines[-5:] if stdout_lines else ["Unknown error"]
        raise RuntimeError("下载失败: 未找到下载文件\n" + "\n".join(err_lines))

    filename = sorted(new_files)[-1]
    filepath = output_dir / filename
    size_mb = round(filepath.stat().st_size / 1024 / 1024, 1)

    # 提取标题
    title = filename.rsplit(".", 1)[0][:100]
    m = re.search(r"标题:\s*(.+?)(?:\n|$)", stdout_full)
    if m:
        title = m.group(1).strip()[:120]
    else:
        m = re.search(r"\[download\]\s+Destination:\s*(.+\.mp4)", stdout_full)
        if m:
            title = Path(m.group(1)).stem[:100]

    vid_match = re.search(r"(\d{15,})", filename)
    actual_video_id = vid_match.group(1) if vid_match else filename.rsplit(".", 1)[0]

    # 平台识别
    platform = "unknown"
    plat_patterns = {
        "douyin": r"(douyin\.com|iesdouyin\.com)",
        "youtube": r"(youtube\.com|youtu\.be)",
        "bilibili": r"bilibili\.com",
        "tiktok": r"tiktok\.com",
    }
    for plat, pat in plat_patterns.items():
        if re.search(pat, url, re.I):
            platform = plat
            break

    # 提取互动数据（来自 vdl.py 的 METRICS 输出行）
    metrics = {"likes": 0, "comments": 0, "shares": 0, "plays": 0, "collects": 0}
    m = re.search(r'METRICS:(\{.+\})', stdout_full)
    if m:
        try:
            raw = json.loads(m.group(1))
            metrics = {
                "likes": raw.get("digg_count", 0),
                "comments": raw.get("comment_count", 0),
                "shares": raw.get("share_count", 0),
                "plays": raw.get("play_count", 0),
                "collects": raw.get("collect_count", 0),
            }
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        "video_id": actual_video_id,
        "title": title,
        "platform": platform,
        "url": url,
        "filename": filename,
        "file_size_mb": size_mb,
        "metrics": metrics,
    }
