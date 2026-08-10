"""
语音转写服务：使用 faster-whisper 模型转写视频音频。
TODO: Phase 2.10 改造为调用 scripts/transcribe.py 子进程模式。
"""
import json
import time
from pathlib import Path
from server.config import MODELS_DIR, SCRIPTS_DIR


def transcribe_video_file(video_path: Path, output_json_path: Path,
                          progress_callback=None) -> dict:
    """转写单个视频文件，返回转写结果 dict。
    Args:
        progress_callback: Optional callable(int percent) 0-100.
    """
    print(f"[transcriber {time.strftime('%H:%M:%S')}] 开始: {video_path}")
    t0 = time.time()

    # 检测 CUDA 可用性
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        print(f"[transcriber {time.strftime('%H:%M:%S')}] CUDA: {cuda_ok}")
    except Exception as e:
        print(f"[transcriber] torch check failed: {e}")
        cuda_ok = False

    device = "cuda" if cuda_ok else "cpu"
    compute_type = "float16" if cuda_ok else "int8"

    print(f"[transcriber] 加载 faster-whisper large-v3-turbo, device={device}")
    from faster_whisper import WhisperModel

    model = WhisperModel(str(MODELS_DIR), device=device, compute_type=compute_type)
    print(f"[transcriber] 模型加载完成, 耗时 {time.time()-t0:.1f}s")

    if progress_callback:
        progress_callback(5)

    segments_list, info = model.transcribe(
        str(video_path),
        beam_size=5,
        language="zh",
        vad_filter=True,
    )

    segments = []
    total_dur = info.duration
    for seg in segments_list:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        if progress_callback and total_dur > 0:
            pct = min(int(seg.end / total_dur * 90) + 5, 94)
            progress_callback(pct)

    if progress_callback:
        progress_callback(100)

    char_count = sum(len(s["text"]) for s in segments)
    result = {
        "video_id": Path(output_json_path).parent.name,
        "language": info.language,
        "duration": round(info.duration, 1),
        "segments": segments,
        "char_count": char_count,
        "segment_count": len(segments),
    }

    output_json_path = Path(output_json_path)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"[transcriber] 完成, 耗时 {elapsed:.1f}s, {len(segments)} segs, {char_count} chars")
    return result
