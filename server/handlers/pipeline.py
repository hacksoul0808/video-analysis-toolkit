"""
管道 Handler：POST /api/process, POST /api/download, POST /api/transcribe,
GET /api/progress。
"""
import json
import os
import shutil
import time
import traceback
from datetime import datetime
from urllib.parse import parse_qs

from server.config import VIDEOS_DIR, COMPRESSION_ENABLED
from server.repository import load_library, save_library, find_video, get_all_tags, update_tags_system
from server.services.downloader import download_video, progress_store
from server.services.transcriber import transcribe_video_file
from server.services.analyzer import analyze_transcript, call_deepseek
from server.services.compressor import process_video_dir, check_ffmpeg


def handle_progress(handler):
    """GET /api/progress?video_id="""
    query = parse_qs(handler.parsed.query)
    video_id = query.get("video_id", [None])[0]
    if video_id and video_id in progress_store:
        _send_json(handler, progress_store[video_id])
    else:
        _send_json(handler, {"percent": 0, "status": "unknown"})


def handle_download(handler, body: dict):
    """POST /api/download"""
    url = body.get("url", "").strip()
    if not url:
        return _send_json(handler, {"error": "请提供视频链接"}, 400)

    video_id = body.get("video_id") or str(int(time.time() * 1000))
    video_dir = VIDEOS_DIR / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    info = download_video(url, video_dir, video_id)

    # 如果实际 video_id 不同，重命名目录
    if info["video_id"] != video_id:
        new_dir = VIDEOS_DIR / info["video_id"]
        if new_dir.exists():
            shutil.rmtree(str(new_dir))
        video_dir.rename(new_dir)
        video_id = info["video_id"]
        video_dir = new_dir

    # 展平文件
    all_mp4 = list(video_dir.rglob("*.mp4"))
    if all_mp4 and all_mp4[0].parent != video_dir:
        shutil.move(str(all_mp4[0]), str(video_dir / all_mp4[0].name))
    for d in sorted(video_dir.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    info["video_id"] = video_id
    _send_json(handler, info)


def handle_transcribe(handler, body: dict):
    """POST /api/transcribe"""
    video_id = body.get("video_id", "").strip()
    if not video_id:
        return _send_json(handler, {"error": "请提供 video_id"}, 400)

    video_dir = VIDEOS_DIR / video_id
    mp4_files = list(video_dir.glob("*.mp4"))
    if not mp4_files:
        return _send_json(handler, {"error": "视频文件不存在，请先下载"}, 404)

    progress_store[video_id] = {"percent": 0, "status": "transcribing", "step": "transcribe"}

    def on_progress(pct):
        progress_store[video_id] = {"percent": pct, "status": "transcribing", "step": "transcribe"}

    output = video_dir / "transcript.json"
    result = transcribe_video_file(mp4_files[0], output, progress_callback=on_progress)
    progress_store[video_id] = {"percent": 100, "status": "done", "step": "transcribe"}

    lib = load_library()
    for v in lib.get("videos", []):
        if v.get("id") == video_id:
            v["transcript_status"] = "done"
            if not v.get("title") or v.get("title") == video_id:
                v["title"] = result.get("title", video_id)
            break
    save_library(lib)

    _send_json(handler, {
        "status": "done",
        "char_count": result["char_count"],
        "segment_count": result["segment_count"],
        "duration_sec": result["duration"],
        "language": result["language"],
    })


def handle_process(handler, body: dict):
    """POST /api/process — 全自动管道: 下载 → 转写 → 分析。"""
    url = body.get("url", "").strip()
    mode = body.get("mode", "full")
    video_id = body.get("video_id", str(int(time.time() * 1000)))

    if not url:
        return _send_json(handler, {"error": "请提供视频链接"}, 400)

    print(f"[pipeline {time.strftime('%H:%M:%S')}] ═══ 开始: {video_id}, mode={mode} ═══")
    pipe_t0 = time.time()
    video_dir = VIDEOS_DIR / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    steps = []
    old_vid = None

    # Step 1: 下载
    try:
        info = download_video(url, video_dir, video_id)
        if info["video_id"] != video_id:
            old_vid = video_id
            new_dir = VIDEOS_DIR / info["video_id"]
            if new_dir.exists():
                shutil.rmtree(str(new_dir))
            video_dir.rename(new_dir)
            video_id = info["video_id"]
            video_dir = new_dir
            if old_vid in progress_store:
                progress_store[video_id] = dict(progress_store[old_vid])

        all_mp4 = list(video_dir.rglob("*.mp4"))
        if all_mp4 and all_mp4[0].parent != video_dir:
            shutil.move(str(all_mp4[0]), str(video_dir / all_mp4[0].name))
        for d in sorted(video_dir.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

        steps.append({"step": "download", "status": "done", "info": info})
    except Exception as e:
        steps.append({"step": "download", "status": "error", "error": str(e)})
        return _send_json(handler, {"status": "error", "steps": steps, "video_id": video_id}, 200)

    if mode == "download_only":
        _save_to_library(video_id, info, steps, None, None)
        print(f"[pipeline] 完成 (download_only), 总耗时 {time.time()-pipe_t0:.1f}s")
        return _send_json(handler, {"status": "done", "steps": steps, "video_id": video_id})

    # Step 2: 转写
    transcript = None
    try:
        mp4_files = list(video_dir.glob("*.mp4"))
        output = video_dir / "transcript.json"
        progress_store[video_id] = {"percent": 0, "status": "transcribing", "step": "transcribe"}

        def on_pipe_progress(pct):
            entry = {"percent": pct, "status": "transcribing", "step": "transcribe"}
            progress_store[video_id] = entry
            if old_vid:
                progress_store[old_vid] = entry

        transcript = transcribe_video_file(mp4_files[0], output, progress_callback=on_pipe_progress)
        progress_store[video_id] = {"percent": 100, "status": "done", "step": "transcribe"}
        if old_vid:
            progress_store[old_vid] = {"percent": 100, "status": "done", "step": "transcribe"}
        steps.append({"step": "transcribe", "status": "done",
                      "char_count": transcript["char_count"], "duration": transcript["duration"]})
    except Exception as e:
        traceback.print_exc()
        steps.append({"step": "transcribe", "status": "error", "error": str(e)})
        return _send_json(handler, {"status": "error", "steps": steps, "video_id": video_id}, 200)

    # Step 3: 本地关键词分析
    script_stats = analyze_transcript(transcript) if transcript else None
    if script_stats:
        analysis_path = video_dir / "script_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(script_stats, f, ensure_ascii=False, indent=2)
    steps.append({"step": "script_analysis", "status": "done"})

    if mode == "download_transcribe":
        _save_to_library(video_id, info, steps, transcript, script_stats)
        print(f"[pipeline] 完成 (download_transcribe), 总耗时 {time.time()-pipe_t0:.1f}s")
        return _send_json(handler, {"status": "done", "steps": steps, "video_id": video_id})

    # Step 4: DeepSeek AI 分析
    video_info_dict = {
        "title": info.get("title", ""),
        "platform": info.get("platform", "unknown"),
        "url": url,
        "file_size_mb": info.get("file_size_mb", 0),
    }
    try:
        progress_store[video_id] = {"percent": 50, "status": "analyzing", "step": "analyze"}
        if old_vid:
            progress_store[old_vid] = {"percent": 50, "status": "analyzing", "step": "analyze"}
        ds_result = call_deepseek(video_info_dict, transcript, script_stats)
        if ds_result.get("error"):
            progress_store[video_id] = {"percent": 100, "status": "error", "step": "analyze"}
            steps.append({"step": "ai_analysis", "status": "error", "error": ds_result["error"]})
        else:
            progress_store[video_id] = {"percent": 100, "status": "done", "step": "analyze"}
            report_path = video_dir / "deepseek_report.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(ds_result["report"])
            if ds_result.get("tags"):
                update_tags_system(ds_result["tags"])
            steps.append({"step": "ai_analysis", "status": "done",
                          "viral_score": ds_result["viral_score"], "tags": ds_result["tags"]})
    except Exception as e:
        traceback.print_exc()
        progress_store[video_id] = {"percent": 100, "status": "error", "step": "analyze"}
        steps.append({"step": "ai_analysis", "status": "error", "error": str(e)})

    _save_to_library(video_id, info, steps, transcript, script_stats,
                     ds_result if 'ds_result' in dir() else None)

    # Step 5: 压缩视频 + 提取封面
    if COMPRESSION_ENABLED and check_ffmpeg():
        try:
            progress_store[video_id] = {"percent": 90, "status": "compressing", "step": "compress"}
            comp_result = process_video_dir(video_dir)
            if comp_result:
                lib = load_library()
                find_video(lib, video_id)
                # 更新 library 中所有 videos 的压缩字段（先找到再更新）
                for v in lib.get("videos", []):
                    if v.get("id") == video_id:
                        v["compressed"] = True
                        v["original_size_mb"] = comp_result["original_size_mb"]
                        v["compressed_size_mb"] = comp_result["compressed_size_mb"]
                        v["compression_ratio"] = comp_result["ratio"]
                        v["has_cover"] = comp_result["has_cover"]
                        if comp_result["has_cover"]:
                            v["cover_file"] = comp_result["cover_file"]
                        break
                save_library(lib)
                steps.append({"step": "compression", "status": "done", "comp": comp_result})
                print(f"[pipeline] 压缩完成: "
                      f"{comp_result['original_size_mb']}MB → {comp_result['compressed_size_mb']}MB "
                      f"({comp_result['ratio'] * 100:.0f}%)")
            else:
                steps.append({"step": "compression", "status": "skipped", "reason": "无 mp4 文件"})
        except Exception as e:
            traceback.print_exc()
            steps.append({"step": "compression", "status": "error", "error": str(e)})
            print(f"[pipeline] 压缩失败: {e}")
    else:
        steps.append({"step": "compression", "status": "skipped", "reason": "压缩未启用或 FFmpeg 不可用"})

    print(f"[pipeline] ═══ 完成, 总耗时 {time.time()-pipe_t0:.1f}s ═══")
    _send_json(handler, {"status": "done", "steps": steps, "video_id": video_id})


def _save_to_library(video_id, info, steps, transcript=None, script_stats=None, ds_result=None):
    """将管道结果保存到 library.json。"""
    lib = load_library()
    entry = find_video(lib, video_id)

    if not entry:
        entry = {
            "id": video_id,
            "url": info.get("url", ""),
            "title": info.get("title", ""),
            "platform": info.get("platform", "unknown"),
            "file_size_mb": info.get("file_size_mb", 0),
            "download_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "transcript_status": "pending",
            "analysis_status": "pending",
            "deepseek_status": "pending",
            "tags": [],
            "viral_score": 0,
            "metrics": {},
            "script_stats": {},
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        lib["videos"].append(entry)

    if transcript:
        entry["transcript_status"] = "done"
        entry["script_stats"] = script_stats or {}
        entry["duration_sec"] = transcript.get("duration", 0)

    if ds_result and not ds_result.get("error"):
        entry["deepseek_status"] = "done"
        entry["analysis_status"] = "done"
        entry["tags"] = ds_result.get("tags", [])
        entry["viral_score"] = ds_result.get("viral_score", 0)
    elif ds_result and ds_result.get("error"):
        entry["deepseek_status"] = "error"

    save_library(lib)


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
