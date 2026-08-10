"""
标签 Handler：GET /api/tags, POST /api/tags (rename/delete/merge)。
"""
import json
from server.repository import load_tags, save_tags, load_library, save_library, get_all_tags


def handle_get(handler):
    """GET /api/tags"""
    _send_json(handler, {"tags": get_all_tags()})


def handle_post(handler, body: dict):
    """POST /api/tags — rename / delete / merge"""
    action = body.get("action", "")
    tag = body.get("tag", "").strip()
    new_tag = body.get("new_tag", "").strip()

    if not action or not tag:
        return _send_json(handler, {"error": "请提供 action 和 tag 参数"}, 400)

    tags_data = load_tags()
    all_tags = tags_data.get("tags", {})

    if action == "rename":
        if not new_tag or new_tag == tag:
            return _send_json(handler, {"error": "新标签名不能为空或相同"}, 400)
        if tag in all_tags:
            count = all_tags.pop(tag)
            all_tags[new_tag] = all_tags.get(new_tag, 0) + count
            tags_data["tags"] = all_tags
            save_tags(tags_data)
            # 同步 library.json
            lib = load_library()
            for v in lib.get("videos", []):
                if tag in v.get("tags", []):
                    v["tags"] = [new_tag if x == tag else x for x in v["tags"]]
            save_library(lib)
            _send_json(handler, {"status": "renamed", "count": count})
        else:
            _send_json(handler, {"error": "标签不存在"}, 404)

    elif action == "delete":
        if tag in all_tags:
            count = all_tags.pop(tag)
            tags_data["tags"] = all_tags
            save_tags(tags_data)
            lib = load_library()
            for v in lib.get("videos", []):
                if tag in v.get("tags", []):
                    v["tags"] = [x for x in v["tags"] if x != tag]
            save_library(lib)
            _send_json(handler, {"status": "deleted", "count": count})
        else:
            _send_json(handler, {"error": "标签不存在"}, 404)

    elif action == "merge":
        into = body.get("into", "").strip()
        if not into:
            return _send_json(handler, {"error": "请提供 into 参数（合并目标标签）"}, 400)
        if tag not in all_tags:
            return _send_json(handler, {"error": f"标签 '{tag}' 不存在"}, 404)
        src_count = all_tags.pop(tag)
        all_tags[into] = all_tags.get(into, 0) + src_count
        tags_data["tags"] = all_tags
        save_tags(tags_data)
        lib = load_library()
        for v in lib.get("videos", []):
            if tag in v.get("tags", []):
                v["tags"] = list(set([into if x == tag else x for x in v["tags"]]))
        save_library(lib)
        _send_json(handler, {"status": "merged", "count": src_count, "into": into})

    else:
        _send_json(handler, {"error": f"未知操作: {action}，支持: rename, delete, merge"}, 400)


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
