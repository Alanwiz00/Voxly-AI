import asyncio
import httpx
from tavily import TavilyClient
from core.config import settings

_tavily: TavilyClient | None = None


def get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        _tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily


async def search_topic_urls(topic_name: str, keywords: str | None, max_results: int = 8) -> list[str]:
    query = f"{topic_name} {keywords or ''}".strip()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: get_tavily().search(query=query, max_results=max_results, search_depth="advanced"),
    )
    return [r["url"] for r in results.get("results", []) if r.get("url")]


async def extract_content(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",
                headers={"Accept": "text/markdown", "X-Return-Format": "markdown"},
            )
            resp.raise_for_status()
            return resp.text[:8000]
    except Exception:
        return None


async def crawl_topic(topic_name: str, keywords: str | None) -> list[dict]:
    urls = await search_topic_urls(topic_name, keywords)
    tasks = [extract_content(url) for url in urls]
    contents = await asyncio.gather(*tasks)

    results = []
    for url, content in zip(urls, contents):
        if content:
            results.append({"url": url, "content": content})
    return results
