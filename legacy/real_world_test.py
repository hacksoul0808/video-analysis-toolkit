#!/usr/bin/env python3
"""
Real-world crawling comparison: curl_cffi vs Playwright vs Crawl4AI

Tests:
  1. Bilibili 视频页 — 提取视频标题、播放量、UP主
  2. Twitter/X 帖子 — 提取推文内容、视频链接
  3. YouTube 视频页 — 提取标题、描述、视频格式
  4. Hacker News 首页 — 提取前 10 条新闻标题和链接
  5. arXiv 论文页 — 提取标题、摘要、作者
  6. 抖音视频 — 提取视频信息 + 实际下载

Run: cd ~/download_video && source .venv-test/bin/activate && python real_world_test.py
"""
import asyncio
import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

RESULTS_DIR = Path(__file__).parent / "realworld_results"
RESULTS_DIR.mkdir(exist_ok=True)

@dataclass
class TestResult:
    test: str
    framework: str
    time_sec: float = 0
    success: bool = False
    extracted: dict = field(default_factory=dict)
    error: str = ""


# ================================================================
# Helpers
# ================================================================
def get_curl_session():
    from curl_cffi import requests as cf
    return cf.Session(impersonate="chrome120")

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


# ================================================================
# Test 1: Bilibili Video
# ================================================================
BILI_URL = "https://www.bilibili.com/video/BV1GJ411x7h7"  # 经典视频

async def test_bili_curl():
    s = get_curl_session()
    t0 = time.time()
    r = s.get(BILI_URL, timeout=15, headers={"User-Agent": DESKTOP_UA})
    elapsed = time.time() - t0
    html = r.text
    title = re.search(r'<title[^>]*>([^<]+)</title>', html)
    title = title.group(1) if title else ""
    # og:video viewCount
    views = re.search(r'"viewCount"\s*:\s*(\d+)', html) or re.search(r'"view"\s*:\s*(\d+)', html)
    author = re.search(r'"author"\s*:\s*"([^"]+)"', html) or re.search(r'"name"\s*:\s*"([^"]+)"', html)
    return TestResult("bilibili", "curl_cffi", elapsed,
                       bool(title),
                       {"title": title[:60], "views": views.group(1) if views else "?",
                        "author": (author.group(1) if author else "?")[:30]})

async def test_bili_playwright():
    from playwright.async_api import async_playwright
    t0 = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page(user_agent=DESKTOP_UA)
        await pg.goto(BILI_URL, wait_until="domcontentloaded", timeout=15000)
        html = await pg.content()
        title = await pg.title()
        await b.close()
    elapsed = time.time() - t0
    views = re.search(r'"viewCount"\s*:\s*(\d+)', html) or re.search(r'"view"\s*:\s*(\d+)', html)
    author = re.search(r'"author"\s*:\s*"([^"]+)"', html) or re.search(r'"name"\s*:\s*"([^"]+)"', html)
    return TestResult("bilibili", "playwright", elapsed,
                       bool(title),
                       {"title": title[:60], "views": views.group(1) if views else "?",
                        "author": (author.group(1) if author else "?")[:30]})

async def test_bili_crawl4ai():
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    t0 = time.time()
    bc = BrowserConfig(headless=True, user_agent=DESKTOP_UA)
    async with AsyncWebCrawler(config=bc) as crawler:
        r = await crawler.arun(url=BILI_URL, config=CrawlerRunConfig())
    elapsed = time.time() - t0
    html = r.html or ""
    md = r.markdown or ""
    title_m = re.search(r'<title[^>]*>([^<]+)</title>', html)
    title = title_m.group(1) if title_m else md[:60]
    media = (r.media or {}).get('videos', [])
    return TestResult("bilibili", "crawl4ai", elapsed,
                       bool(title),
                       {"title": title[:60], "auto_media": len(media),
                        "markdown_len": len(md)})


# ================================================================
# Test 2: Hacker News (structured list extraction)
# ================================================================
HN_URL = "https://news.ycombinator.com/"

async def test_hn_curl():
    s = get_curl_session()
    t0 = time.time()
    r = s.get(HN_URL, timeout=10)
    elapsed = time.time() - t0
    # Extract top stories
    stories = re.findall(r'class="titleline"><a href="([^"]*)"[^>]*>([^<]+)</a>', r.text)
    return TestResult("hackernews", "curl_cffi", elapsed,
                       len(stories) >= 10,
                       {"story_count": len(stories),
                        "top3": [{"title": s[1][:50], "url": s[0][:60]} for s in stories[:3]]})

async def test_hn_playwright():
    from playwright.async_api import async_playwright
    t0 = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto(HN_URL, wait_until="domcontentloaded", timeout=10000)
        stories = await pg.evaluate("""
            () => [...document.querySelectorAll('.titleline > a')]
                .slice(0, 10)
                .map(a => ({title: a.textContent, url: a.href}))
        """)
        await b.close()
    elapsed = time.time() - t0
    return TestResult("hackernews", "playwright", elapsed,
                       len(stories) >= 10,
                       {"story_count": len(stories),
                        "top3": [{"title": s["title"][:50], "url": s["url"][:60]} for s in stories[:3]]})

async def test_hn_crawl4ai():
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    t0 = time.time()
    bc = BrowserConfig(headless=True)
    async with AsyncWebCrawler(config=bc) as crawler:
        r = await crawler.arun(url=HN_URL, config=CrawlerRunConfig())
    elapsed = time.time() - t0
    md = r.markdown or ""
    # Count links in markdown
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', md)
    # Filter to actual story links (not HN navigation)
    stories = [(t, u) for t, u in links if len(t) > 10 and not u.startswith("https://news.ycombinator")]
    return TestResult("hackernews", "crawl4ai", elapsed,
                       len(stories) >= 5,
                       {"link_count": len(links), "story_count": len(stories),
                        "top3": [{"title": s[0][:50], "url": s[1][:60]} for s in stories[:3]],
                        "markdown_len": len(md)})


# ================================================================
# Test 3: arXiv Paper
# ================================================================
ARXIV_URL = "https://arxiv.org/abs/2506.06218"  # a recent paper

async def test_arxiv_curl():
    s = get_curl_session()
    t0 = time.time()
    r = s.get(ARXIV_URL, timeout=10)
    elapsed = time.time() - t0
    title = re.search(r'<meta name="citation_title" content="([^"]+)"', r.text)
    authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', r.text)
    abstract = re.search(r'<blockquote class="abstract[^"]*">\s*<span[^>]*>Abstract:</span>\s*(.*?)</blockquote>', r.text, re.DOTALL)
    return TestResult("arxiv", "curl_cffi", elapsed,
                       bool(title),
                       {"title": (title.group(1) if title else "?")[:80],
                        "authors": authors[:5],
                        "abstract": (abstract.group(1).strip() if abstract else "?")[:200]})

async def test_arxiv_playwright():
    from playwright.async_api import async_playwright
    t0 = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto(ARXIV_URL, wait_until="domcontentloaded", timeout=10000)
        data = await pg.evaluate("""
            () => ({
                title: document.querySelector('.title')?.textContent?.replace('Title:', '').trim() || '',
                authors: [...document.querySelectorAll('.authors a')].map(a => a.textContent).slice(0, 5),
                abstract: document.querySelector('.abstract')?.textContent?.replace('Abstract:', '').trim()?.substring(0, 200) || '',
            })
        """)
        await b.close()
    elapsed = time.time() - t0
    return TestResult("arxiv", "playwright", elapsed,
                       bool(data.get("title")),
                       {"title": data["title"][:80], "authors": data["authors"],
                        "abstract": data["abstract"][:200]})

async def test_arxiv_crawl4ai():
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    t0 = time.time()
    bc = BrowserConfig(headless=True)
    async with AsyncWebCrawler(config=bc) as crawler:
        r = await crawler.arun(url=ARXIV_URL, config=CrawlerRunConfig())
    elapsed = time.time() - t0
    md = r.markdown or ""
    # Try to find title and abstract in markdown
    has_title = len(md) > 100  # If we got substantial content
    # Count links extracted
    links = (r.links or {}) if hasattr(r, 'links') else {}
    return TestResult("arxiv", "crawl4ai", elapsed,
                       has_title,
                       {"markdown_len": len(md),
                        "markdown_preview": md[:300],
                        "links_count": len(links.get("internal", [])) + len(links.get("external", [])) if isinstance(links, dict) else 0})


# ================================================================
# Test 4: GitHub repo page
# ================================================================
GH_URL = "https://github.com/browser-use/browser-use"

async def test_gh_curl():
    s = get_curl_session()
    t0 = time.time()
    r = s.get(GH_URL, timeout=10, headers={"User-Agent": DESKTOP_UA})
    elapsed = time.time() - t0
    stars = re.search(r'stargazers.*?>([\d,.]+[kKmM]?)', r.text) or re.search(r'(\d[\d,.]*)\s*stars', r.text)
    desc = re.search(r'<meta name="description" content="([^"]+)"', r.text)
    lang = re.findall(r'programmingLanguage">\s*([^<]+)', r.text)
    return TestResult("github", "curl_cffi", elapsed,
                       bool(desc),
                       {"desc": (desc.group(1) if desc else "?")[:100],
                        "stars": stars.group(1) if stars else "?",
                        "languages": lang[:5]})

async def test_gh_playwright():
    from playwright.async_api import async_playwright
    t0 = time.time()
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page(user_agent=DESKTOP_UA)
        await pg.goto(GH_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)
        data = await pg.evaluate("""
            () => ({
                desc: document.querySelector('[class*="About"] p, .f4.my-3')?.textContent?.trim() ||
                      document.querySelector('meta[name="description"]')?.content || '',
                stars: document.querySelector('#repo-stars-counter-star')?.textContent?.trim() || '?',
                topics: [...document.querySelectorAll('.topic-tag')].map(t => t.textContent.trim()).slice(0, 5),
            })
        """)
        await b.close()
    elapsed = time.time() - t0
    return TestResult("github", "playwright", elapsed,
                       bool(data.get("desc")),
                       {"desc": data["desc"][:100], "stars": data["stars"],
                        "topics": data["topics"]})

async def test_gh_crawl4ai():
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    t0 = time.time()
    bc = BrowserConfig(headless=True, user_agent=DESKTOP_UA)
    async with AsyncWebCrawler(config=bc) as crawler:
        r = await crawler.arun(url=GH_URL, config=CrawlerRunConfig())
    elapsed = time.time() - t0
    md = r.markdown or ""
    has_content = "browser" in md.lower() and len(md) > 500
    return TestResult("github", "crawl4ai", elapsed,
                       has_content,
                       {"markdown_len": len(md),
                        "markdown_preview": md[:300]})


# ================================================================
# Test 5: 抖音视频 (full pipeline: extract + download)
# ================================================================
DOUYIN_URL = "https://www.iesdouyin.com/share/video/7628940941864324394/"

async def test_douyin_curl_download():
    """Full pipeline: extract video_id → download MP4"""
    s = get_curl_session()
    t0 = time.time()

    # Step 1: Get video info
    r = s.get(DOUYIN_URL, timeout=15, headers={"User-Agent": MOBILE_UA})
    m = re.search(r'video_id=([a-zA-Z0-9_]+)', r.text)
    internal_id = m.group(1) if m else None
    tm = re.search(r'"desc"\s*:\s*"([^"]*)"', r.text)
    title = (tm.group(1).encode().decode('unicode_escape') if tm and '\\u' in tm.group(1) else (tm.group(1) if tm else ""))[:60]

    if not internal_id:
        return TestResult("douyin_download", "curl_cffi", time.time()-t0, False, error="No video_id")

    # Step 2: Download first 1MB to test speed
    play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={internal_id}&ratio=720p&line=0"
    dl_start = time.time()
    dr = s.get(play_url, timeout=30, allow_redirects=True)
    dl_time = time.time() - dl_start
    size_mb = len(dr.content) / 1024 / 1024
    speed = size_mb / dl_time if dl_time > 0 else 0

    elapsed = time.time() - t0
    return TestResult("douyin_download", "curl_cffi", elapsed,
                       dr.status_code == 200 and size_mb > 1,
                       {"title": title, "video_id": internal_id,
                        "size_mb": round(size_mb, 1), "dl_time": round(dl_time, 1),
                        "speed_mbps": round(speed, 1)})


# ================================================================
# Main
# ================================================================
async def main():
    all_results = []

    tests = [
        # (name, functions)
        ("Bilibili Video", [test_bili_curl, test_bili_playwright, test_bili_crawl4ai]),
        ("Hacker News", [test_hn_curl, test_hn_playwright, test_hn_crawl4ai]),
        ("arXiv Paper", [test_arxiv_curl, test_arxiv_playwright, test_arxiv_crawl4ai]),
        ("GitHub Repo", [test_gh_curl, test_gh_playwright, test_gh_crawl4ai]),
        ("Douyin Download", [test_douyin_curl_download]),
    ]

    for group_name, funcs in tests:
        print(f"\n{'='*65}")
        print(f"  {group_name}")
        print(f"{'='*65}")

        for func in funcs:
            try:
                r = await func()
                all_results.append(r)
                ok = "✅" if r.success else "❌"
                print(f"  {r.framework:<14} {r.time_sec:>5.1f}s {ok}  {json.dumps(r.extracted, ensure_ascii=False, default=str)[:120]}")
            except Exception as e:
                r = TestResult(group_name, func.__name__.split('_')[1], error=str(e)[:200])
                all_results.append(r)
                print(f"  {func.__name__:<30} ERROR: {str(e)[:80]}")

    # ---- Grand Summary ----
    print(f"\n\n{'='*75}")
    print("REAL-WORLD CRAWLING BENCHMARK — GRAND SUMMARY")
    print(f"{'='*75}")
    print(f"\n{'Site':<20} {'curl_cffi':>12} {'Playwright':>12} {'Crawl4AI':>12}")
    print("-" * 60)

    by_test = {}
    for r in all_results:
        by_test.setdefault(r.test, {})[r.framework] = r

    for test_name, frameworks in by_test.items():
        row = f"  {test_name:<18}"
        for fw in ["curl_cffi", "playwright", "crawl4ai"]:
            r = frameworks.get(fw)
            if r:
                ok = "✅" if r.success else "❌"
                row += f" {ok} {r.time_sec:>4.1f}s    "
            else:
                row += "     -        "
        print(row)

    # Stats
    for fw in ["curl_cffi", "playwright", "crawl4ai"]:
        fw_results = [r for r in all_results if r.framework == fw]
        success = sum(1 for r in fw_results if r.success)
        avg_time = sum(r.time_sec for r in fw_results) / max(len(fw_results), 1)
        print(f"\n  {fw}: {success}/{len(fw_results)} success, avg {avg_time:.1f}s")

    # Save
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump([asdict(r) for r in all_results], f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved to {RESULTS_DIR}/results.json")


if __name__ == "__main__":
    asyncio.run(main())
