"""
统计服务：计算视频库的总体统计数据。
"""
def compute_stats(videos: list[dict]) -> dict:
    """从视频列表计算 KPI、分组统计、分数分布。"""
    total = len(videos)
    if total == 0:
        return {"total_videos": 0, "by_tag": {}, "avg_viral_score": 0}

    avg_score = round(sum(v.get("viral_score", 0) for v in videos) / total, 1)

    # 按标签分组统计
    by_tag: dict[str, dict] = {}
    for v in videos:
        for t in v.get("tags", []):
            if t not in by_tag:
                by_tag[t] = {"count": 0, "total_score": 0, "total_likes": 0}
            by_tag[t]["count"] += 1
            by_tag[t]["total_score"] += v.get("viral_score", 0)
            by_tag[t]["total_likes"] += v.get("metrics", {}).get("likes", 0)

    for t in by_tag:
        c = by_tag[t]["count"]
        by_tag[t]["avg_score"] = round(by_tag[t]["total_score"] / c, 1) if c else 0
        by_tag[t]["avg_likes"] = round(by_tag[t]["total_likes"] / c, 1) if c else 0

    # 分数分布
    score_dist = {"爆款(80+)": 0, "优质(60-79)": 0, "普通(40-59)": 0, "低迷(<40)": 0}
    for v in videos:
        s = v.get("viral_score", 0)
        if s >= 80:
            score_dist["爆款(80+)"] += 1
        elif s >= 60:
            score_dist["优质(60-79)"] += 1
        elif s >= 40:
            score_dist["普通(40-59)"] += 1
        else:
            score_dist["低迷(<40)"] += 1

    return {
        "total_videos": total,
        "avg_viral_score": avg_score,
        "by_tag": by_tag,
        "score_distribution": score_dist,
    }
