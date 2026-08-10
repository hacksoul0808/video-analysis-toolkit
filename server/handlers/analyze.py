"""
分析 Handler：POST /api/analyze, POST /api/batch-analyze。
"""
import json
import time
from server.config import VIDEOS_DIR
from server.repository import load_library, save_library, find_video, update_tags_system
from server.services.analyzer import analyze_transcript, call_deepseek


def handle_analyze(handler, body: dict):
    """POST /api/analyze"""
    video_id = body.get("video_id", "").strip()
    if not video_id:
        return _send_json(handler, {"error": "请提供 video_id"}, 400)

    print(f"[analyze {time.strftime('%H:%M:%S')}] 开始: {video_id}")
    video_dir = VIDEOS_DIR / video_id

    # 加载转写
    transcript_path = video_dir / "transcript.json"
    if not transcript_path.exists():
        return _send_json(handler, {"error": "转写文件不存在，请先转写"}, 404)

    with open(transcript_path, encoding="utf-8") as f:
        transcript = json.load(f)

    # 本地关键词分析
    script_stats = analyze_transcript(transcript)
    if script_stats:
        analysis_path = video_dir / "script_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(script_stats, f, ensure_ascii=False, indent=2)

    # 加载视频信息
    lib = load_library()
    video_info = find_video(lib, video_id)
    if not video_info:
        lib_files = list(video_dir.glob("*.mp4"))
        video_info = {
            "title": lib_files[0].stem if lib_files else video_id,
            "platform": "unknown",
        }

    # 调用 DeepSeek
    result = call_deepseek(video_info, transcript, script_stats)

    if result["error"]:
        return _send_json(handler, result, 200)

    # 保存报告
    report_path = video_dir / "deepseek_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result["report"])

    if result["tags"]:
        update_tags_system(result["tags"])

    # 更新 library
    entry = find_video(lib, video_id)
    if entry:
        entry["tags"] = result["tags"]
        entry["viral_score"] = result["viral_score"]
        entry["deepseek_status"] = "done"
        entry["transcript_status"] = "done"
        entry["analysis_status"] = "done"
        if script_stats:
            entry["script_stats"] = script_stats
            entry["duration_sec"] = script_stats["duration"]
    else:
        lib["videos"].append({
            "id": video_id,
            "url": video_info.get("url", ""),
            "title": video_info.get("title", ""),
            "platform": video_info.get("platform", "unknown"),
            "duration_sec": script_stats["duration"] if script_stats else 0,
            "file_size_mb": video_info.get("file_size_mb", 0),
            "tags": result["tags"],
            "viral_score": result["viral_score"],
            "script_stats": script_stats,
            "deepseek_status": "done",
            "transcript_status": "done",
            "analysis_status": "done",
            "metrics": video_info.get("metrics", {}),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    save_library(lib)

    _send_json(handler, {
        "status": "done",
        "viral_score": result["viral_score"],
        "tags": result["tags"],
    })


def handle_batch(handler, body: dict):
    """POST /api/batch-analyze"""
    video_ids = body.get("video_ids", [])
    if not video_ids:
        return _send_json(handler, {"error": "请提供 video_ids 列表"}, 400)

    results = []
    for vid in video_ids:
        try:
            handle_analyze(handler, {"video_id": vid})
            results.append({"video_id": vid, "status": "done"})
        except Exception as e:
            results.append({"video_id": vid, "status": "error", "error": str(e)})

    _send_json(handler, {"status": "done", "results": results, "total": len(video_ids)})


def _send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except OSError:
        pass
