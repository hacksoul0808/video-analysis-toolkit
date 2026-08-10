#!/usr/bin/env python3
"""
脚本深度分析工具

分析转写脚本的语速、关键词密度、开场钩子、情绪词等指标。

用法:
  python3 analyze_scripts.py --transcripts web_demo/all_transcripts.json --output web_demo/script_analysis.json
"""

import argparse
import json
import re
from pathlib import Path

# 关键词列表
AI_KEYWORDS = [
    "transformer", "attention", "模型", "训练", "推理", "参数",
    "token", "embedding", "loss", "gradient", "optimizer",
    "GPT", "BERT", "LLM", "大模型", "神经网络", "深度学习",
    "卷积", "残差", "归一化", "softmax", "向量", "矩阵",
    "encoder", "decoder", "self-attention", "multi-head",
    "fine-tune", "微调", "预训练", "prompt", "inference",
]

EMOTION_KEYWORDS = [
    "震惊", "颠覆", "疯", "杀疯", "爆", "炸", "恐怖",
    "太强了", "牛", "厉害", "amazing", "incredible",
    "可怕", "惊人", "离谱", "逆天", "绝了", "炸裂",
    "突破", "革命", "划时代", "史上最",
]

TECH_KEYWORDS = [
    "CVPR", "ICLR", "NeurIPS", "ICML", "AAAI",
    "开源", "论文", "实验", "数据集", "benchmark",
    "GPU", "CUDA", "API", "GitHub", "代码",
    "准确率", "精度", "性能", "效率", "速度",
]


def analyze_transcript(transcript_data, video_data=None):
    """分析单个视频的脚本"""
    segments = transcript_data.get("segments", [])
    if not segments:
        return None

    full_text = " ".join(s["text"] for s in segments)
    char_count = len(full_text.replace(" ", ""))
    duration = transcript_data.get("duration", 0)

    # 语速 (chars per minute)
    chars_per_min = round(char_count / (duration / 60)) if duration > 0 else 0

    # 关键词统计
    text_lower = full_text.lower()
    ai_count = sum(1 for kw in AI_KEYWORDS if kw.lower() in text_lower)
    emotion_count = sum(1 for kw in EMOTION_KEYWORDS if kw in full_text)
    tech_count = sum(1 for kw in TECH_KEYWORDS if kw in full_text or kw.lower() in text_lower)

    # 开场钩子 (前30秒)
    hook_segments = [s for s in segments if s["start"] < 30]
    hook_text = " ".join(s["text"] for s in hook_segments)

    # 结尾 (最后30秒)
    close_segments = [s for s in segments if s["start"] > duration - 30] if duration > 30 else []
    close_text = " ".join(s["text"] for s in close_segments)

    return {
        "char_count": char_count,
        "duration": round(duration, 1),
        "chars_per_min": chars_per_min,
        "segment_count": len(segments),
        "avg_seg_chars": round(char_count / len(segments)) if segments else 0,
        "ai_keywords": ai_count,
        "emotion_keywords": emotion_count,
        "tech_keywords": tech_count,
        "keyword_density_pct": round((ai_count + emotion_count + tech_count) / char_count * 100, 2) if char_count > 0 else 0,
        "hook_text": hook_text[:300],
        "close_text": close_text[:300],
    }


def main():
    parser = argparse.ArgumentParser(description="脚本深度分析")
    parser.add_argument("--transcripts", "-t", required=True, help="转写 JSON 文件")
    parser.add_argument("--output", "-o", default="script_analysis.json", help="输出文件")
    args = parser.parse_args()

    with open(args.transcripts, encoding="utf-8") as f:
        transcripts = json.load(f)

    print(f"Analyzing {len(transcripts)} transcripts...")

    results = {}
    for vid, data in transcripts.items():
        analysis = analyze_transcript(data)
        if analysis:
            results[vid] = analysis
            cpm = analysis["chars_per_min"]
            cpm_status = "optimal" if 295 <= cpm <= 315 else ("fast" if cpm > 320 else "slow")
            print(f"  {vid}: {analysis['char_count']} chars, {cpm} cpm ({cpm_status}), "
                  f"AI={analysis['ai_keywords']} EMO={analysis['emotion_keywords']} TECH={analysis['tech_keywords']}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis complete: {len(results)} videos → {output_path}")

    # Summary stats
    if results:
        avg_cpm = sum(r["chars_per_min"] for r in results.values()) / len(results)
        avg_ai = sum(r["ai_keywords"] for r in results.values()) / len(results)
        avg_emo = sum(r["emotion_keywords"] for r in results.values()) / len(results)
        print(f"\nAverages: {avg_cpm:.0f} chars/min, {avg_ai:.1f} AI keywords, {avg_emo:.1f} emotion words")


if __name__ == "__main__":
    main()
