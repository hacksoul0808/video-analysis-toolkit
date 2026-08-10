#!/usr/bin/env python3
"""
批量视频语音转写工具 (faster-whisper)

将视频目录中的所有 MP4 文件转写为带时间戳的文本。

用法:
  python3 transcribe_videos.py --input videos/user_all/ --output web_demo/all_transcripts.json
  python3 transcribe_videos.py --input videos/user_all/ --model large-v3 --device cuda
"""

import argparse
import json
import re
import time
from pathlib import Path


def transcribe_video(model, video_path):
    """转写单个视频，返回 segments 列表"""
    segments, info = model.transcribe(
        str(video_path),
        beam_size=5,
        language="zh",
        vad_filter=True,
    )

    result = []
    for seg in segments:
        result.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    return result, info


def main():
    parser = argparse.ArgumentParser(description="批量视频语音转写")
    parser.add_argument("--input", "-i", required=True, help="视频目录")
    parser.add_argument("--output", "-o", default="all_transcripts.json", help="输出 JSON 文件")
    parser.add_argument("--model", default=str(Path(__file__).parent / "Model"), help="Whisper 模型路径")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="设备")
    parser.add_argument("--compute-type", default="float16", help="计算精度 (default: float16)")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    input_dir = Path(args.input)
    videos = sorted(input_dir.glob("*.mp4"))

    if not videos:
        print(f"No MP4 files found in {input_dir}")
        return

    print(f"Found {len(videos)} videos in {input_dir}")
    print(f"Loading model: {args.model} on {args.device} ({args.compute_type})")

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    all_transcripts = {}
    total_chars = 0
    total_segments = 0

    for i, video_path in enumerate(videos):
        # Extract video ID from filename
        m = re.search(r"(\d{18,})", video_path.name)
        vid = m.group(1) if m else video_path.stem

        print(f"\n[{i+1}/{len(videos)}] {video_path.name[:60]}...")
        t0 = time.time()

        try:
            segments, info = transcribe_video(model, video_path)
            elapsed = time.time() - t0

            char_count = sum(len(s["text"]) for s in segments)
            total_chars += char_count
            total_segments += len(segments)

            all_transcripts[vid] = {
                "video_id": vid,
                "filename": video_path.name,
                "language": info.language,
                "duration": round(info.duration, 1),
                "segments": segments,
                "char_count": char_count,
                "segment_count": len(segments),
            }

            print(f"  ✓ {len(segments)} segments, {char_count} chars, {elapsed:.1f}s")

        except Exception as e:
            print(f"  ✗ Error: {e}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_transcripts, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Transcription complete!")
    print(f"  Videos: {len(all_transcripts)}/{len(videos)}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Total segments: {total_segments:,}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
