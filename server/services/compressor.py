"""
视频压缩服务：提取封面 + H.265 压缩 + 替换原文件。
"""
import subprocess
import time
from pathlib import Path


# ── FFmpeg 可用性检查 ──────────────────────────
_ffmpeg_checked = False
FFMPEG_AVAILABLE = False


def check_ffmpeg() -> bool:
    """检查 FFmpeg 是否可用（仅检查一次，缓存结果）。"""
    global _ffmpeg_checked, FFMPEG_AVAILABLE
    if _ffmpeg_checked:
        return FFMPEG_AVAILABLE
    _ffmpeg_checked = True
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        if result.returncode == 0:
            FFMPEG_AVAILABLE = True
            print(f"[compressor] FFmpeg 可用")
            return True
        else:
            print(f"[compressor] FFmpeg 不可用, rc={result.returncode}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        print(f"[compressor] FFmpeg 不可用 (未安装或不可执行)")
        return False


# ── 封面提取 ────────────────────────────────────
def extract_cover(video_path: Path, output_dir: Path,
                  time_offset: str = "00:00:01") -> Path | None:
    """从视频指定时间点截取一帧保存为 cover.jpg。失败返回 None。"""
    if not check_ffmpeg():
        return None

    cover_path = output_dir / "cover.jpg"
    print(f"[compressor {time.strftime('%H:%M:%S')}] 提取封面: {video_path.name}")

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", time_offset,
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(cover_path),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        if result.returncode == 0 and cover_path.exists() and cover_path.stat().st_size > 0:
            print(f"[compressor] 封面提取成功: cover.jpg ({cover_path.stat().st_size / 1024:.1f}KB)")
            return cover_path
        else:
            print(f"[compressor] 封面提取失败: {result.stderr[-300:]}")
            return None
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[compressor] 封面提取异常: {e}")
        return None


# ── 视频压缩 ────────────────────────────────────
def compress_video(
    input_path: Path,
    output_dir: Path,
    resolution: str = "480p",
    crf: int = 32,
    codec: str = "libx265",
    audio_bitrate: str = "64k",
) -> dict:
    """
    压缩视频：480p H.265 CRF 32。
    步骤：输出到临时文件 → 校验大小 → 覆盖原文件。
    返回：{"original_size_mb", "compressed_size_mb", "ratio"}
    失败抛出 RuntimeError。
    """
    if not check_ffmpeg():
        raise RuntimeError("FFmpeg 不可用")

    # 解析分辨率
    scale_map = {"480p": "-2:480", "720p": "-2:720", "1080p": "-2:1080"}
    scale = scale_map.get(resolution, "-2:480")

    temp_path = output_dir / f"_compressed_{int(time.time())}.mp4"
    original_size = input_path.stat().st_size

    print(f"[compressor {time.strftime('%H:%M:%S')}] 压缩: {input_path.name} "
          f"({original_size / 1024 / 1024:.1f}MB) → {resolution} H.265 CRF {crf}")

    t0 = time.time()
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-c:v", codec, "-crf", str(crf), "-preset", "fast",
                "-vf", f"scale={scale}",
                "-c:a", "aac", "-b:a", audio_bitrate,
                "-movflags", "+faststart",
                str(temp_path),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"FFmpeg 压缩失败 (rc={result.returncode}): {result.stderr[-500:]}")

        if not temp_path.exists() or temp_path.stat().st_size == 0:
            raise RuntimeError("压缩输出文件为空或不存在")

        compressed_size = temp_path.stat().st_size
        ratio = round(1 - compressed_size / original_size, 3)

        # 覆盖原文件
        input_path.unlink()
        temp_path.rename(input_path)

        print(f"[compressor] 压缩完成: {compressed_size / 1024 / 1024:.1f}MB "
              f"({ratio * 100:.0f}% 压缩率), 耗时 {elapsed:.1f}s")

        return {
            "original_size_mb": round(original_size / 1024 / 1024, 1),
            "compressed_size_mb": round(compressed_size / 1024 / 1024, 1),
            "ratio": ratio,
        }

    except (subprocess.TimeoutExpired, OSError) as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"压缩异常: {e}")


# ── 一键处理 ────────────────────────────────────
def process_video_dir(video_dir: Path) -> dict | None:
    """
    一键处理视频目录：提取封面 + 压缩 + 返回结果。
    供 pipeline 和批量脚本共同调用。
    返回 None 表示跳过（无 mp4 或 FFmpeg 不可用）。
    """
    if not check_ffmpeg():
        return None

    mp4_files = list(video_dir.glob("*.mp4"))
    if not mp4_files:
        print(f"[compressor] 跳过 {video_dir.name}: 无 mp4 文件")
        return None

    video_path = mp4_files[0]
    result = {"original_size_mb": 0, "compressed_size_mb": 0, "ratio": 0, "has_cover": False, "cover_file": ""}

    # Step 1: 提取封面（用原片）
    cover_path = extract_cover(video_path, video_dir)
    if cover_path:
        result["has_cover"] = True
        result["cover_file"] = "cover.jpg"

    # Step 2: 压缩视频
    comp_result = compress_video(video_path, video_dir)
    result.update(comp_result)

    return result
