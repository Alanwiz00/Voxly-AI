import asyncio
from datetime import datetime, timezone

import httpx
import trafilatura
from ddgs import DDGS

from core.config import settings


# ── Source: DuckDuckGo ────────────────────────────────────────────────────────

async def _search_ddgs(query: str, max_results: int) -> list[dict]:
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=max_results)),
        )
        return [{"url": r["href"], "date": None, "source": "web"} for r in results if r.get("href")]
    except Exception:
        return []


# ── Source: Reddit public JSON API (no key required) ─────────────────────────

async def _search_reddit(query: str, max_results: int) -> list[dict]:
    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": "voxly-content-bot/1.0"}
    params = {"q": query, "sort": "new", "limit": max_results * 2, "t": "month", "type": "link"}
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                return []

        posts = resp.json().get("data", {}).get("children", [])
        results: list[dict] = []
        for post in posts:
            d = post.get("data", {})
            selftext = d.get("selftext", "").strip()
            permalink = d.get("permalink", "")
            post_url = d.get("url", "")
            created = d.get("created_utc", 0)
            post_date = datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else None

            if selftext and len(selftext) > 100:
                # Self-post with substantial body — use inline content, no need to fetch
                results.append({
                    "url": f"https://reddit.com{permalink}",
                    "content": f"{d.get('title', '')}\n\n{selftext[:5000]}",
                    "date": post_date,
                    "source": "reddit",
                })
            elif post_url and not post_url.startswith("https://www.reddit.com") and not post_url.startswith("https://reddit.com"):
                # Link post — queue the external URL for trafilatura extraction
                results.append({"url": post_url, "date": post_date, "source": "reddit"})

            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


# ── Source: NewsAPI (requires NEWS_API_KEY) ───────────────────────────────────

async def _search_newsapi(query: str, api_key: str, max_results: int) -> list[dict]:
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": max_results,
        "apiKey": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
        articles = resp.json().get("articles", [])
        results = []
        for a in articles:
            article_url = a.get("url", "")
            if not article_url or article_url == "[Removed]":
                continue
            inline = "\n\n".join(
                filter(None, [a.get("title"), a.get("description"), (a.get("content") or "")[:3000]])
            )
            results.append({
                "url": article_url,
                "content": inline or None,
                "date": a.get("publishedAt"),
                "source": "newsapi",
            })
        return results
    except Exception:
        return []


# ── Content extraction via trafilatura ───────────────────────────────────────

def _trafilatura_extract(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return ""
    return trafilatura.extract(downloaded, output_format="markdown", include_links=False) or ""


async def extract_content(url: str) -> str | None:
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _trafilatura_extract, url)
        return text[:8000] if text.strip() else None
    except Exception:
        return None


# ── Main entry point ─────────────────────────────────────────────────────────

async def crawl_topic(topic_name: str, keywords: str | None) -> list[dict]:
    """
    Crawl a topic across multiple sources (DuckDuckGo, Reddit, NewsAPI) and
    return a deduplicated list of dicts with url, content, date, and source.
    NewsAPI is only used when NEWS_API_KEY is configured.
    """
    query = f"{topic_name} {keywords or ''}".strip()

    # --- Gather candidate items from all sources concurrently ---
    news_task = (
        _search_newsapi(query, settings.NEWS_API_KEY, max_results=5)
        if settings.NEWS_API_KEY
        else _empty()
    )
    ddgs_results, reddit_results, news_results = await asyncio.gather(
        _search_ddgs(query, max_results=6),
        _search_reddit(query, max_results=4),
        news_task,
    )

    # --- Deduplicate by URL; prioritise sources with pre-extracted content ---
    seen: set[str] = set()
    pre_extracted: list[dict] = []   # already have content
    need_extraction: list[dict] = [] # need trafilatura

    # Priority order: NewsAPI > Reddit > DuckDuckGo
    for item in [*news_results, *reddit_results, *ddgs_results]:
        url = (item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        if item.get("content"):
            pre_extracted.append(item)
        else:
            need_extraction.append(item)

    # Extract content for URL-only items (cap total at 12 sources)
    slots = max(0, 12 - len(pre_extracted))
    targets = need_extraction[:slots]
    extracted_texts = await asyncio.gather(*[extract_content(i["url"]) for i in targets])

    for item, text in zip(targets, extracted_texts):
        if text:
            pre_extracted.append({**item, "content": text})

    return pre_extracted


async def _empty() -> list:
    return []
