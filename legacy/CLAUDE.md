# download_video - 视频下载工具集

## 项目经验总结

### 抖音下载核心发现
1. **海外 IP 限制**: `douyin.com` 主站会触发验证码，但 `iesdouyin.com` 分享页不会
2. **无水印下载**: `aweme.snssdk.com/aweme/v1/play/` (不是 `playwm`) = 无水印
3. **TLS 指纹**: 必须用 `curl_cffi` impersonate Chrome，普通 requests 会被拦截
4. **API 空响应**: douyin.com 的 API 需要 `__ac_signature` 等 token，海外直接调返回空
5. **Playwright API 拦截**: iesdouyin 移动分享页会自动调 `/aweme/post` API，Playwright 拦截这个请求是获取用户视频列表最可靠的方式
6. **视频质量**: snssdk CDN 默认 720p，更高清需要 Cookie + API

### 技术路径
```
短链接 → curl_cffi 302 跟随 → 提取 video_id
→ iesdouyin.com/share/video/{id}/ → 正则提取 internal video_id
→ aweme.snssdk.com/aweme/v1/play/?video_id={internal_id}&ratio=720p → MP4
```

### 工具链
- `curl_cffi`: TLS 指纹模拟，绕过 bot 检测
- `Playwright`: 用于 API 拦截（不是页面渲染），获取用户视频列表
- `yt-dlp`: 通用兜底，1900+ 站点（但抖音海外失败）
- `Crawl4AI`: AI 爬虫框架，Playwright 封装，适合通用场景
- `lux`: Go 二进制，中国平台支持好，但抖音海外也失败

### 文件结构
- `vdl.py` - 通用下载入口（自动识别平台+引擎）
- `download_douyin.py` - 抖音单视频无水印下载
- `crawl_user_videos.py` - 抖音用户批量爬取+下载
- `benchmark.py` - 性能测试
- `bench_crawl4ai.py` - Crawl4AI 测试
- `REPORT.md` - 完整测评报告

### 性能基线
- 单视频: 6.6s / 21.5MB / 3.3 MB/s (720p 无水印)
- 批量 3 个: 23.3s / 56.6MB / 2.4 MB/s
- Playwright 用户页渲染: ~5s 获取 15 个视频列表

### 已知限制
- Python 3.10 环境，browser-use 需要 3.11+
- 海外 IP，douyin.com 触发验证码
- 720p 上限（无 Cookie 情况下）

### AI 浏览器自动化框架测评 (2026-04-18)

#### 测评结果

| 任务 | curl_cffi | Playwright | Crawl4AI | browser-use |
|------|:---------:|:----------:|:--------:|:-----------:|
| **单视频提取** | ✅ 1.4s | ✅ 2.9s | ✅ 3.2s | ❌ 不兼容 |
| **用户页发现** | N/A | ✅ 14.2s (15视频) | ✅ 5.2s (仅用户名) | ❌ 不兼容 |

#### 各框架评价

**curl_cffi** (推荐用于已知 API)
- 最快 (1.4s)，无浏览器开销
- 需要 `impersonate="chrome120"` 模拟 TLS 指纹
- 适合：知道 API 路径的确定性任务

**Playwright** (推荐用于动态页面 + API 拦截)
- API 拦截能力最强，能捕获完整视频列表 (15/15)
- 需要自己写 response handler 逻辑
- 适合：需要 JS 渲染 + 网络拦截的场景

**Crawl4AI** (推荐用于通用爬取)
- 自动提取 media 元素（发现了 video src）
- 用户页只能获取静态 HTML（视频列表需要 JS 加载）
- 适合：快速原型、AI 辅助内容提取

**browser-use** (0.12.6 - 暂不推荐)
- ❌ 与 AWS Bedrock Converse API 不兼容 (tool_call 格式问题)
- ❌ `ainvoke` monkey-patch 与 langchain pydantic v2 冲突
- ❌ 即使连接成功也解析失败 ("items" error)
- 适合：有 OpenAI API key 的场景（原生支持最好）
- 修复方式：需要 `model_config = {"extra": "allow", "protected_namespaces": ()}`
  + `object.__setattr__(llm, 'provider', 'anthropic')` 等 hack

**BrowserOS** (不适用)
- 桌面应用 (TypeScript/Chromium fork)，不是 Python 库
- 不能在 headless Linux 服务器上运行
- 适合：个人桌面使用，不适合自动化脚本

#### 结论
对于 "给一个链接自动爬取所有视频" 的需求：
1. **确定性路径** (知道 API): curl_cffi > Playwright > Crawl4AI
2. **探索性路径** (未知页面): Crawl4AI > Playwright > browser-use (需 OpenAI key)
3. **生产级批量**: Playwright API intercept (最可靠的视频列表获取)

browser-use 的 AI agent 理念很好，但工程成熟度不够——对 LLM provider 的耦合太紧，
Bedrock/非 OpenAI 场景问题多。等它稳定后再考虑。

#### 测试环境
- `.venv-test/` (Python 3.12, browser-use 0.12.6, crawl4ai 0.8.6)
- `test_all_frameworks.py` - 完整测试脚本
- `framework_benchmark/final_results.json` - 结果数据

### 多站点实测对比 (2026-04-18)

#### 测试结果

| 网站 | curl_cffi | Playwright | Crawl4AI |
|------|:---------:|:----------:|:--------:|
| **Bilibili** | ✅ 0.8s | ✅ 2.0s | ✅ 1.5s |
| **Hacker News** | ✅ 0.1s | ✅ 0.6s | ✅ 1.1s |
| **arXiv 论文** | ✅ 0.2s | ✅ 0.7s | ✅ 1.3s |
| **GitHub Repo** | ✅ 0.5s | ✅ 3.4s | ✅ 1.9s |
| **抖音下载** | ✅ 14.3s (含21MB) | — | — |

#### 关键发现
1. **curl_cffi 全场最快**: 静态页面平均 0.4s，比 Playwright 快 4x，比 Crawl4AI 快 3x
2. **三框架 100% 成功率**: Bilibili/HN/arXiv/GitHub 都成功（无严重反爬）
3. **Bilibili 海外受限**: 三个框架都只拿到 "出错啦!" 页面（海外 IP 限制）
4. **Crawl4AI 自动提取强**: HN 自动提取 197 链接/29 新闻；GitHub 43K 字 Markdown
5. **抖音管道稳定**: 14.3s 完成提取+下载，1.5 MB/s

#### 场景推荐（更新版）
| 场景 | 最佳选择 | 原因 |
|------|---------|------|
| **已知 API / 结构化爬取** | curl_cffi | 最快，最省资源，TLS 指纹模拟 |
| **JS 渲染 + 网络拦截** | Playwright | API intercept 无可替代 |
| **快速原型 / 通用内容提取** | Crawl4AI | 自动 Markdown + 媒体提取 |
| **反爬严重站点** | curl_cffi 首选 + Playwright 备选 | TLS 指纹 > 浏览器开销 |
| **AI 辅助探索未知页面** | Crawl4AI > Playwright | 自动结构化输出 |

#### 测试文件
- `real_world_test.py` - 多站点对比脚本
- `realworld_results/results.json` - 结果数据

### 抖音博主分析经验 (2026-04-19)

#### 数据获取方式
1. 短链接 → curl_cffi 302 跟随 → 提取 `sec_uid`
2. Playwright 渲染 `iesdouyin.com/share/user/{sec_uid}` → 拦截 `/web/api/v2/aweme/post/` API → 获取视频列表 (含 digg_count)
3. 逐个访问 `iesdouyin.com/share/video/{id}/` → curl_cffi 正则提取补充数据 (评论/分享/收藏/时长/发布时间)

#### 踩坑记录
- **Playwright API 拦截不稳定**: 同一代码有时能触发 API 有时不能，可能与 cookie/web_id 有关
- **API 返回数据不完整**: 海外 IP 调用时 `play_count=0`, `comment_count=0`, `share_count=0`，需要逐个访问视频页补充
- **`text_extra` 可能为 None**: `v.get('text_extra') or []` 而不是 `v.get('text_extra', [])`，因为值可能是 `None` 而非缺失
- **response.body() 必须在 browser.close() 之前调用**: 关闭后读取会报错
- **iesdouyin 主页现在 301 到 douyin.com**: `iesdouyin.com/` → `douyin.com/?redirect_from=iesdouyin`，但 share/user/ 路径仍然有效
- **直接调用 API 返回空**: `curl_cffi` 直接请求 `/web/api/v2/aweme/post/` 返回空 body，必须通过页面 JS 触发

#### 分析指标体系
- **收藏/赞比** (干货指标): >40% 表示内容有长期存档价值（Lau博士 44.6%，远高于行业 10-15%）
- **分享/赞比** (传播力): >15% 表示强传播力（Lau博士 18.8%）
- **互动率**: (赞+评)/粉丝数，9.2% 属于高互动
- **时长甜蜜点**: 5-8分钟效果最好，<3分钟信息量不足，>10分钟完播率下降
- **月度趋势**: 按月聚合观察涨粉趋势和内容策略变化

#### 博主画像: Lau博士的云组会
- **定位**: AI论文精读 + 硬核科普（学术↔大众桥梁）
- **数据**: 7.7万粉 | 15个视频 | avg ❤4,270 | 收藏率44.6%
- **爆款公式**: 知名模型/公司 + 颠覆性结论 + 情绪标题 → ❤14K
- **哑弹特征**: 软广(豆包❤57) 或小众产品(TicNote❤315) 严重拉低
- **发布频率**: ~1条/周，质量优先

#### 脚本转写与分析 (2026-04-19)

**工具链**: faster-whisper large-v3 + GPU (CUDA float16)
- 安装坑: `pip install` 默认装到系统 python3.10，需要 `python -m ensurepip` 再 `python -m pip install`
- 14 个视频总计 ~5 分钟转写完成，31,456 字，2,667 个时间戳段落
- 语言检测自动识别中文，准确率 >99%

**脚本分析发现**:
- **语速甜蜜点**: 300-310 字/分钟，爆款视频都在此区间
- **开场钩子 4 种公式**: 恐惧钩子 / 认知颠覆 / 数据冲击 / 反直觉
- **关键词密度**: 2.4-3.0% 是甜蜜点，过高(>4%)太学术，过低(<1%)缺专业感
- **情绪词数量**: ≥5 次的视频表现显著更好

#### Web Demo
- **URL**: `https://lau.adobefoundry.com` (Cloudflare Named Tunnel)
- **端口**: 8300 (Colligo allowed port)
- **功能**: 仪表盘 + 图表 + 视频播放 + 脚本同步高亮 + 脚本分析
- **技术**: 纯 Python HTTP server, Chart.js, Whisper 转写, ffmpeg 缩略图

#### 文件
- `user_analysis.json` - 完整视频数据（含所有互动指标）
- `web_demo/app.py` - Web Demo 服务器
- `web_demo/all_transcripts.json` - 所有视频转写脚本
- `web_demo/script_analysis.json` - 脚本分析数据
- `web_demo/thumbnails/` - 视频缩略图
- `videos/lau_all/` - 14 个视频文件 (322MB)
