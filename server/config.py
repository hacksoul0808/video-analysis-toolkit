"""
全局配置：路径、环境变量、常量。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # video-analysis-toolkit/

# ── .env 加载 ─────────────────────────────────────
def _load_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val

_load_env()

# 离线模式：所有模型/Tokenizer 均从本地加载，不访问 HuggingFace Hub
os.environ["HF_HUB_OFFLINE"] = "1"

# ── 路径 ──────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
LIBRARY_FILE = DATA_DIR / "library.json"
TAGS_FILE = DATA_DIR / "tags.json"
VIDEOS_DIR = DATA_DIR / "videos"
MODELS_DIR = BASE_DIR / "models" / "whisper-large-v3-turbo"
WEB_DIR = BASE_DIR / "web"
SCRIPTS_DIR = BASE_DIR / "scripts"

PORT = int(os.environ.get("PORT", 8840))

# ── 确保目录存在 ──────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# ── 视频压缩配置 ──────────────────────────────────
COMPRESSION_ENABLED = True        # 是否启用压缩
COMPRESSION_RESOLUTION = "480p"   # 目标分辨率
COMPRESSION_CRF = 32              # H.265 CRF 值
COMPRESSION_CODEC = "libx265"     # 编码器
COMPRESSION_AUDIO_BITRATE = "64k" # 音频码率
EXTRACT_COVER_ENABLED = True      # 是否提取封面
COVER_TIME_OFFSET = "00:00:01"    # 封面截取时间点

# ── AI 分析关键词 ──────────────────────────────────
AI_KEYWORDS = [
    "transformer", "attention", "模型", "训练", "推理", "参数",
    "token", "embedding", "大模型", "神经网络", "深度学习",
    "卷积", "残差", "归一化", "softmax", "向量", "矩阵",
    "encoder", "decoder", "微调", "预训练", "prompt", "inference",
]

EMOTION_KEYWORDS = [
    "震惊", "颠覆", "疯", "杀疯", "爆", "炸", "恐怖",
    "太强了", "牛", "厉害", "可怕", "惊人", "离谱", "逆天",
    "绝了", "炸裂", "突破", "革命", "划时代", "史上最",
]

TECH_KEYWORDS = [
    "CVPR", "ICLR", "NeurIPS", "ICML", "AAAI",
    "开源", "论文", "实验", "数据集", "benchmark",
    "GPU", "CUDA", "API", "GitHub", "代码",
    "准确率", "精度", "性能", "效率", "速度",
]
