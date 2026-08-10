"""
AI 分析服务：本地关键词分析 + DeepSeek API 调用 + 爆款评分。
"""
import os
import re
from server.config import AI_KEYWORDS, EMOTION_KEYWORDS, TECH_KEYWORDS


# ── System Prompt ──────────────────────────────────

SYSTEM_PROMPT = """你是一位顶级短视频文案分析师，曾服务于头部 MCN 机构。你的任务是深度分析视频转写文案，输出可直接落地的爆款方法论。

分析时必须严格遵循以下结构输出 Markdown：

## 🎯 爆款公式拆解
- 开场钩子类型（恐惧/认知颠覆/数据冲击/反直觉，四选一）
- 情绪节奏曲线（标注时间节点）
- 信息密度分布（高/中/低 + 时间区间）
- 标题公式提取（给出可复用的模板）
- 引导转化策略

## 📋 可复制模板
### 标题模板
（含 {占位符} 的模板）
### 结构模板
（Hook-Why-How-CTA 或自定义分步结构）

## 📊 同类对比分析
仅基于提供的参考数据对比（收藏率/分享率/语速/情绪词），给出差异化分析

## 🔧 改进建议
3 条具体可执行的优化建议（标题/节奏/话术）

## 🏷️ 自动标签
从预设标签库中选择 3-6 个最匹配的标签，格式: `#标签1 #标签2`

标签库: 论文精读, 行业热点, 产品测评, 商务合作, 科普教程, 教程向, 收藏向, 传播向, AI, 深度学习, 颠覆性结论, 数据驱动, 认知升级, 实用技巧, 3分钟以内, 5-8分钟, 10分钟以上, 爆款, 优质, 普通, 幽默, 严肃, 温情, 焦虑, 励志"""


# ── 标签清洗 ─────────────────────────────────────

def _clean_tags(raw_tags: list[str]) -> list[str]:
    """过滤掉占位符、空值、纯符号等无效标签，去重后返回。"""
    seen = set()
    cleaned = []
    for t in raw_tags:
        t = t.strip()
        # 跳过空值、纯符号、占位符、超长标签
        if not t or len(t) < 2 or len(t) > 15:
            continue
        if t.startswith("{"):
            continue
        if t in ("#", "##", "###", "## ", "# #"):
            continue
        # 去掉标签末尾的 ` 等符号
        t = t.rstrip("`。．.，,；;：:！!？?）)]}】>")
        if len(t) < 2:
            continue
        if t not in seen:
            seen.add(t)
            cleaned.append(t)
    return cleaned


# ── 本地关键词分析 ─────────────────────────────────

def analyze_transcript(transcript_data: dict) -> dict | None:
    """分析转写文本：语速、关键词、钩子。"""
    segments = transcript_data.get("segments", [])
    if not segments:
        return None

    full_text = " ".join(s["text"] for s in segments)
    char_count = len(full_text.replace(" ", ""))
    duration = transcript_data.get("duration", 0)

    chars_per_min = round(char_count / (duration / 60)) if duration > 0 else 0
    text_lower = full_text.lower()

    ai_count = sum(1 for kw in AI_KEYWORDS if kw.lower() in text_lower)
    emotion_count = sum(1 for kw in EMOTION_KEYWORDS if kw in full_text)
    tech_count = sum(1 for kw in TECH_KEYWORDS if kw in full_text or kw.lower() in text_lower)

    hook_segments = [s for s in segments if s["start"] < 30]
    hook_text = " ".join(s["text"] for s in hook_segments)

    close_segments = [s for s in segments if s["start"] > duration - 30] if duration > 30 else []
    close_text = " ".join(s["text"] for s in close_segments)

    keyword_density = round((ai_count + emotion_count + tech_count) / char_count * 100, 2) if char_count > 0 else 0

    return {
        "char_count": char_count,
        "duration": round(duration, 1),
        "chars_per_min": chars_per_min,
        "segment_count": len(segments),
        "avg_seg_chars": round(char_count / len(segments)) if segments else 0,
        "ai_keywords": ai_count,
        "emotion_keywords": emotion_count,
        "tech_keywords": tech_count,
        "keyword_density": keyword_density,
        "hook_text": hook_text[:300],
        "close_text": close_text[:300],
    }


# ── DeepSeek API 调用 ──────────────────────────────

def call_deepseek(video_info: dict, transcript_data: dict, script_stats: dict | None) -> dict:
    """调用 DeepSeek API 进行文案分析，返回 report + tags + viral_score。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        return {"error": "DeepSeek API Key 未配置", "report": "", "tags": [], "viral_score": 0}

    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "请安装 openai 库: pip install openai", "report": "", "tags": [], "viral_score": 0}

    client = OpenAI(api_key=api_key, base_url=base_url)

    segments = transcript_data.get("segments", [])
    full_text = " ".join(s["text"] for s in segments)
    hook_text = script_stats.get("hook_text", "") if script_stats else ""

    duration = transcript_data.get("duration", 0)
    char_count = script_stats.get("char_count", 0) if script_stats else 0
    cpm = script_stats.get("chars_per_min", 0) if script_stats else 0
    emotion = script_stats.get("emotion_keywords", 0) if script_stats else 0
    kd = script_stats.get("keyword_density", 0) if script_stats else 0

    user_prompt = f"""分析以下短视频文案，参考数据：
- 标题: {video_info.get('title', '未知')}
- 时长: {duration}秒
- 总字数: {char_count}
- 语速: {cpm}字/分钟
- 情绪词数量: {emotion}个
- 关键词密度: {kd}%
- 平台: {video_info.get('platform', '未知')}

开场(前30秒):
{hook_text}

完整转写文本:
{full_text}"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        report = response.choices[0].message.content
    except Exception as e:
        return {"error": f"DeepSeek API 调用失败: {str(e)}", "report": "", "tags": [], "viral_score": 0}

    # 提取标签（从报告全文匹配 #标签 格式，过滤掉占位符和无效值）
    tags = _clean_tags(re.findall(r'#(\S+)', report))
    if not tags:
        m = re.search(r'##\s*🏷️.*?\n(.*?)(?:\n##|\Z)', report, re.DOTALL)
        if m:
            tags = _clean_tags(re.findall(r'#(\S+)', m.group(1)))

    viral_score = _calculate_viral_score(report, script_stats)

    return {"error": None, "report": report, "tags": tags, "viral_score": viral_score}


# ── 爆款评分 ───────────────────────────────────────

def _calculate_viral_score(report: str, script_stats: dict | None) -> int:
    """从报告内容和统计数据中计算 0-100 爆款评分。
    
    评分维度：
    - 钩子类型 (0-20): 认知颠覆/反直觉 > 数据冲击 > 恐惧，无钩子=0
    - 结构完整度 (0-20): Hook + Why + CTA + 模板，每缺一项扣分
    - 情绪词密度 (0-15): 按情绪词数量阶梯评分，0 词 = 0 分
    - 内容数据 (0-25): 基于 script_stats 的语速、AI关键词密度
    - 模板可复用度 (0-20): 报告是否包含可直接使用的模板
    """
    score = 0

    # ── 钩子质量 (0-20) ──
    hook_count = 0
    if "认知颠覆" in report or "反直觉" in report:
        hook_count += 1
        score += 12
    if "数据冲击" in report:
        hook_count += 1
        score += 8
    if "恐惧" in report:
        hook_count += 1
        score += 5
    # 多种钩子叠加有额外加分（多样性奖励）
    if hook_count >= 2:
        score += 3
    # 兜底：什么都没识别到，给一个低分基准
    if hook_count == 0:
        score += 3

    # ── 结构完整度 (0-20) ──
    structure = 0
    if "Hook" in report or "开场" in report or "钩子" in report:
        structure += 1
        score += 6
    if "Why" in report or "为什么" in report:
        structure += 1
        score += 5
    if "CTA" in report or "引导" in report:
        structure += 1
        score += 4
    if "## 📋 可复制模板" in report or "标题模板" in report:
        structure += 1
        score += 5

    # ── 内容数据 (0-25) ──
    if script_stats:
        cpm = script_stats.get("chars_per_min", 0)
        kd = script_stats.get("keyword_density", 0)
        ai_kw = script_stats.get("ai_keywords", 0)
        tech_kw = script_stats.get("tech_keywords", 0)

        # 语速适中 (200-600 字/分钟 是短视频黄金区间)
        if 200 <= cpm <= 600:
            score += 8
        elif cpm > 600:
            score += 4  # 太快
        else:
            score += 3  # 太慢也有一点分

        # AI/技术关键词密度
        total_kw = ai_kw + tech_kw
        if total_kw >= 5:
            score += 10
        elif total_kw >= 3:
            score += 7
        elif total_kw >= 1:
            score += 4

        # 关键词密度
        if kd >= 0.5:
            score += 7
        elif kd >= 0.2:
            score += 4
        elif kd > 0:
            score += 2

    # ── 情绪词密度 (0-15) ──
    if script_stats:
        emo = script_stats.get("emotion_keywords", 0)
        if emo >= 7:
            score += 15
        elif emo >= 5:
            score += 12
        elif emo >= 3:
            score += 8
        elif emo >= 1:
            score += 4
        # emo == 0: 不加分

    # ── 模板可复用度 (0-20) ──
    template_score = 0
    if "{占位符}" in report or "{标题}" in report or "{关键词}" in report or "{变量}" in report:
        template_score += 10
    if "## 📋" in report or "标题模板" in report:
        template_score += 7
    if "结构模板" in report or "Hook-Why-How" in report:
        template_score += 3
    # 如果有真正的模板但没有占位符，说明分析不够结构化
    if "模板" in report and template_score == 0:
        template_score = 3
    score += template_score

    return min(score, 100)
