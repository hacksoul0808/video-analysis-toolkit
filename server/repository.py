"""
数据访问层：library.json / tags.json 的 CRUD 操作。
所有函数都是纯 Python，无 HTTP 依赖。
"""
import json
from datetime import datetime
from server.config import LIBRARY_FILE, TAGS_FILE


# ── Library CRUD ───────────────────────────────────

def load_library():
    """加载视频库索引。"""
    if LIBRARY_FILE.exists():
        with open(LIBRARY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"videos": [], "updated_at": ""}


def save_library(data: dict):
    """保存视频库索引。"""
    data["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_video(library_data: dict, video_id: str) -> dict | None:
    """在库中查找指定视频条目。"""
    for v in library_data.get("videos", []):
        if v.get("id") == video_id:
            return v
    return None


def update_video(library_data: dict, video_id: str, updates: dict):
    """更新库中指定视频的字段，如不存在则添加。"""
    entry = find_video(library_data, video_id)
    if entry:
        entry.update(updates)
    else:
        library_data.setdefault("videos", []).append({"id": video_id, **updates})


def delete_video(library_data: dict, video_id: str) -> dict | None:
    """从库中删除指定视频，返回被删除的条目（用于标签清理）。"""
    videos = library_data.get("videos", [])
    deleted = None
    library_data["videos"] = []
    for v in videos:
        if v.get("id") == video_id:
            deleted = v
        else:
            library_data["videos"].append(v)
    return deleted


# ── Tags CRUD ──────────────────────────────────────

def load_tags() -> dict:
    """加载全局标签体系。"""
    if TAGS_FILE.exists():
        with open(TAGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tags(tags_data: dict):
    """保存全局标签体系。"""
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)


def get_all_tags() -> list[tuple[str, int]]:
    """获取所有标签按使用次数降序排列。"""
    tags_data = load_tags()
    tags = tags_data.get("tags", {})
    return sorted(tags.items(), key=lambda x: -x[1])


def update_tags_system(video_tags: list[str]):
    """根据视频的标签列表更新全局标签计数。"""
    tags_data = load_tags()
    all_tags = tags_data.get("tags", {})

    for tag in video_tags:
        all_tags[tag] = all_tags.get(tag, 0) + 1

    tags_data["tags"] = all_tags
    save_tags(tags_data)


def decrement_tags(tag_list: list[str]):
    """减少指定标签的计数（删除视频时调用）。"""
    if not tag_list:
        return
    tags_data = load_tags()
    all_tags = tags_data.get("tags", {})
    for t in tag_list:
        if t in all_tags:
            all_tags[t] = max(0, all_tags[t] - 1)
            if all_tags[t] <= 0:
                del all_tags[t]
    tags_data["tags"] = all_tags
    save_tags(tags_data)
