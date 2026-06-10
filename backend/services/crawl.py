import asyncio
import trafilatura
from ddgs import DDGS


async def search_topic_urls(topic_name: str, keywords: str | None, max_results: int = 8) -> list[str]:
    query = f"{topic_name} {keywords or ''}".strip()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: list(DDGS().text(query, max_results=max_results)),
    )
    return [r["href"] for r in results if r.get("href")]


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


async def crawl_topic(topic_name: str, keywords: str | None) -> list[dict]:
    urls = await search_topic_urls(topic_name, keywords)
    tasks = [extract_content(url) for url in urls]
    contents = await asyncio.gather(*tasks)

    results = []
    for url, content in zip(urls, contents):
        if content:
            results.append({"url": url, "content": content})
    return results
