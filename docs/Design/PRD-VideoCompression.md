# 产品需求文档：视频压缩存储方案

> **版本**: v1.1（已确认）  
> **日期**: 2026-08-10  
> **状态**: 已完成  

---

## 1. 决策摘要

| # | 问题 | 决策 | 含义 |
|---|------|------|------|
| Q1 | 原片处理 | **B. 替换原片** | 压缩后删除原始 MP4，只保留压缩版 |
| Q2 | 画质等级 | **C. 激进压缩** | 480p / H.265 / CRF 32 / 64k 音频 |
| Q3 | 历史视频 | **B. 批量回溯** | 提供脚本/接口对已有视频批量压缩 |
| Q4 | 文件命名 | **A. 同名覆盖** | 压缩输出到临时文件，成功后覆盖原 MP4 |
| Q5 | 封面提取 | **B. 提取封面** | 压缩前用原片截取第 1 秒画面存为 cover.jpg |

---

## 2. 确认的压缩参数

| 参数 | 值 |
|------|-----|
| 分辨率 | **480p**（`scale=-2:480`） |
| 编码器 | **libx265**（H.265/HEVC） |
| CRF | **32** |
| 音频编码 | **aac, 64k** |
| 预估压缩比 | **80-90%** |
| 100MB 压缩后 | **~10-20MB** |

### FFmpeg 核心命令

```bash
ffmpeg -i input.mp4 \
  -c:v libx265 -crf 32 -preset fast \
  -vf "scale=-2:480" \
  -c:a aac -b:a 64k \
  -movflags +faststart \
  output.mp4
```

> `-movflags +faststart` 保证浏览器渐进播放兼容性。  
> `-preset fast` 平衡压缩速度与压缩率，短视频压缩耗时秒级。

---

## 3. 完整流程

### 3.1 新视频 Pipeline（自动）

```
下载 → 转写 → AI分析 → 提取封面 → 压缩替换 → 更新 library.json
```

1. 下载完成 → 得到 `{id}/xxx.mp4`
2. 转写完成 → 生成 `transcript.json`
3. AI 分析完成 → 生成 `deepseek_report.md`
4. **提取封面** → `ffmpeg -i xxx.mp4 -ss 00:00:01 -vframes 1 cover.jpg`
5. **压缩** → `xxx.mp4` → 临时文件 `xxx_compressed.mp4`
6. **替换** → 删除 `xxx.mp4`，将 `xxx_compressed.mp4` 重命名为原始文件名
7. **记录** → 更新 `library.json` 中的压缩相关字段

### 3.2 历史视频批量压缩（手动触发）

提供独立的 Python 脚本 `scripts/compress_existing.py` 或 API 端点 `POST /api/compress/batch`：

- 扫描 `data/videos/*/` 下所有子目录
- 跳过已标记 `compressed: true` 的视频
- 跳过无 MP4 文件的目录（仅分析产物）
- 顺序执行：提取封面 → 压缩 → 替换 → 更新 library.json
- 支持进度回报

### 3.3 失败处理

- 压缩失败：保留原文件，记录错误日志，不更新 library.json
- FFmpeg 不可用：跳过压缩，前端无明显报错，`library.json` 中有 `compressed: false`
- 封面提取失败：不阻塞压缩流程，仅跳过封面步骤

---

## 4. 数据模型变更

### 4.1 library.json 新增字段

```json
{
  "videos": [
    {
      "id": "7532289168827747647",
      "compressed": true,
      "original_size_mb": 85.3,
      "compressed_size_mb": 12.5,
      "compression_ratio": 0.853,
      "has_cover": true,
      "cover_file": "cover.jpg"
    }
  ]
}
```

### 4.2 视频目录最终结构

```
data/videos/{video_id}/
├── xxx.mp4               ← 压缩后的视频（10-20MB）
├── cover.jpg             ← 封面截图（~50KB）
├── transcript.json       ← 转写文本
├── script_analysis.json  ← 脚本分析
└── deepseek_report.md    ← AI 分析报告
```

---

## 5. 技术实现要点

### 5.1 新增文件

```
server/services/
└── compressor.py          ← 视频压缩 + 封面提取服务（新建，~80行）

scripts/
└── compress_existing.py   ← 历史视频批量压缩脚本（新建，~60行）
```

### 5.2 compressor.py 核心接口

```python
def extract_cover(video_path: Path, output_dir: Path) -> Path | None:
    """从视频第1秒截取一帧保存为 cover.jpg。失败返回 None。"""

def compress_video(input_path: Path, output_dir: Path) -> dict:
    """
    压缩视频：480p H.265 CRF 32。
    步骤：输出到临时文件 → 校验大小 → 覆盖原文件。
    返回：{"original_size_mb", "compressed_size_mb", "ratio"}
    失败抛出 RuntimeError。
    """

def process_video_dir(video_dir: Path) -> dict:
    """
    一键处理视频目录：提取封面 + 压缩 + 返回结果。
    供 pipeline 和批量脚本共同调用。
    """
```

### 5.3 Pipeline 集成点

在 `server/handlers/pipeline.py` 的 `run_full_pipeline()` 末尾，分析成功后插入：

```python
# 分析完成 → 压缩
from server.services.compressor import process_video_dir
result = process_video_dir(video_dir)
repository.update_video(library, video_id, {
    "compressed": True,
    "original_size_mb": result["original_size_mb"],
    "compressed_size_mb": result["compressed_size_mb"],
    "compression_ratio": result["ratio"],
    "has_cover": result.get("has_cover", False),
    "cover_file": result.get("cover_file", ""),
})
```

### 5.4 依赖检查

启动时检查 FFmpeg 是否可用：

```python
import subprocess
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    FFMPEG_AVAILABLE = True
except (FileNotFoundError, subprocess.CalledProcessError):
    FFMPEG_AVAILABLE = False
```

`FFMPEG_AVAILABLE = False` 时，压缩流程静默跳过（不报错、不阻塞 pipeline）。

### 5.5 配置项（server/config.py 新增）

```python
COMPRESSION_ENABLED = True        # 是否启用压缩
COMPRESSION_RESOLUTION = "480p"   # 目标分辨率
COMPRESSION_CRF = 32              # H.265 CRF 值
COMPRESSION_CODEC = "libx265"     # 编码器
COMPRESSION_AUDIO_BITRATE = "64k" # 音频码率
EXTRACT_COVER_ENABLED = True      # 是否提取封面
COVER_TIME_OFFSET = "00:00:01"    # 封面截取时间点
```

---

## 6. 前端改动（最小化）

| 改动点 | 描述 |
|--------|------|
| 视频卡片 | 若有 `cover.jpg`，优先使用该封面替代占位图 |
| 视频详情 | 播放器表现不变（压缩后仍为 .mp4，浏览器直接播放） |
| 统计面板 | 可选：显示 `总压缩节省空间` 统计 |

---

## 7. 验收标准

- [ ] 新视频 Pipeline 完成后，MP4 文件大小 < 20MB（原 100MB 时）
- [ ] 压缩后视频可在浏览器正常播放
- [ ] `cover.jpg` 生成成功，可在前端卡片渲染
- [ ] `library.json` 中 `compressed` 字段正确标记
- [ ] 批量脚本可对历史 4 个视频一次性完成压缩
- [ ] FFmpeg 不可用时，pipeline 不阻塞、不报错
- [ ] 压缩失败时原文件不被删除

---

> **下一手**：需求已确认，请 @vibe-maker 基于本 PRD 实施开发 —— 新建 `server/services/compressor.py`、`scripts/compress_existing.py`，修改 `server/handlers/pipeline.py`、`server/config.py`、`server/repository.py`（新增压缩字段写入），以及前端封面展示逻辑。
