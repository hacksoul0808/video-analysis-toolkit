"""
方法论聚合服务：跨视频提炼钩子模式、标题模板、高分案例。
"""
import json
import re
from server.config import VIDEOS_DIR


def aggregate_methodology(library_data: dict, tag_filter: str | None = None) -> dict:
    """聚合所有已分析视频的爆款模式，可选按标签筛选。"""
    videos = library_data.get("videos", [])
    if tag_filter:
        videos = [v for v in videos if tag_filter in v.get("tags", [])]

    all_hooks: dict[str, int] = {}
    all_templates: list[str] = []
    best_examples: list[dict] = []

    for v in videos:
        vid = v["id"]
        report_path = VIDEOS_DIR / vid / "deepseek_report.md"
        if not report_path.exists():
            continue

        with open(report_path, encoding="utf-8") as f:
            report = f.read()

        # 提取钩子类型
        hook_match = re.search(r'开场钩子类型[：:]\s*(\S+)', report)
        if hook_match:
            hook_type = hook_match.group(1)
            all_hooks[hook_type] = all_hooks.get(hook_type, 0) + 1

        # 提取标题模板
        tmpl_matches = re.findall(r'[「"{]([^「"{]*?\{[^}]*?\}[^」"}]*?)[」"}]', report)
        for t in tmpl_matches[:3]:
            if len(t) > 5 and t not in all_templates:
                all_templates.append(t)

        # 高分案例
        if v.get("viral_score", 0) >= 75 and len(best_examples) < 5:
            best_examples.append({
                "id": vid,
                "title": v.get("title", ""),
                "viral_score": v.get("viral_score", 0),
                "tags": v.get("tags", []),
            })

    return {
        "hook_patterns": sorted(all_hooks.items(), key=lambda x: -x[1]),
        "title_templates": all_templates[:10],
        "best_examples": best_examples,
        "total_analyzed": len(videos),
    }
