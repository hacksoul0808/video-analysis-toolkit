"""
批量压缩历史视频：扫描 data/videos/*/ 下所有目录，压缩已完成分析的视频。
用法：python scripts/compress_existing.py
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.config import VIDEOS_DIR
from server.repository import load_library, save_library
from server.services.compressor import process_video_dir, check_ffmpeg


def batch_compress():
    """扫描并压缩所有历史视频。"""
    if not check_ffmpeg():
        print("错误: FFmpeg 不可用，请先安装 FFmpeg")
        return

    lib = load_library()
    videos = lib.get("videos", [])
    video_dirs = sorted(VIDEOS_DIR.iterdir())

    if not video_dirs:
        print("没有找到视频目录")
        return

    print(f"\n发现 {len(video_dirs)} 个视频目录，开始批量压缩...\n")

    compressed_count = 0
    skipped_count = 0
    error_count = 0
    total_original = 0
    total_compressed = 0
    t0 = time.time()

    for video_dir in video_dirs:
        if not video_dir.is_dir():
            continue
        vid = video_dir.name

        # 检查是否已压缩
        already_compressed = False
        for v in videos:
            if v.get("id") == vid and v.get("compressed"):
                already_compressed = True
                break

        if already_compressed:
            print(f"[{vid}] 跳过: 已压缩")
            skipped_count += 1
            continue

        mp4_files = list(video_dir.glob("*.mp4"))
        if not mp4_files:
            print(f"[{vid}] 跳过: 无 mp4 文件")
            skipped_count += 1
            continue

        size_mb = mp4_files[0].stat().st_size / 1024 / 1024
        print(f"[{vid}] 压缩中... (原大小: {size_mb:.1f}MB)")

        try:
            result = process_video_dir(video_dir)
            if result:
                # 更新 library.json
                for v in lib.get("videos", []):
                    if v.get("id") == vid:
                        v["compressed"] = True
                        v["original_size_mb"] = result["original_size_mb"]
                        v["compressed_size_mb"] = result["compressed_size_mb"]
                        v["compression_ratio"] = result["ratio"]
                        v["has_cover"] = result["has_cover"]
                        if result["has_cover"]:
                            v["cover_file"] = result["cover_file"]
                        break
                compressed_count += 1
                total_original += result["original_size_mb"]
                total_compressed += result["compressed_size_mb"]
                print(f"  → 压缩完成: {result['original_size_mb']}MB → {result['compressed_size_mb']}MB "
                      f"({result['ratio'] * 100:.0f}%)")
            else:
                skipped_count += 1
        except Exception as e:
            error_count += 1
            print(f"  → 压缩失败: {e}")

    save_library(lib)
    elapsed = time.time() - t0

    print(f"\n{'=' * 50}")
    print(f"批量压缩完成!")
    print(f"  压缩: {compressed_count}  跳过: {skipped_count}  失败: {error_count}")
    if total_original > 0:
        saved = round(total_original - total_compressed, 1)
        ratio = round((total_original - total_compressed) / total_original * 100)
        print(f"  总原始大小: {total_original}MB → 总压缩大小: {total_compressed}MB")
        print(f"  共节省: {saved}MB ({ratio}%)")
    print(f"  总耗时: {elapsed:.1f}s")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    batch_compress()
