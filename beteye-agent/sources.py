"""Content sources: news RSS, YouTube RSS + transcripts, X accounts via Nitter RSS."""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import feedparser

log = logging.getLogger("beteye.sources")

# ---------------------------------------------------------------------------
# Default source lists (all overridable via env)
# ---------------------------------------------------------------------------

# News RSS — current football news, tournament updates
NEWS_FEEDS: list[str] = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml",          # BBC Sport
    "https://www.theguardian.com/football/rss",                  # The Guardian
    "https://www.skysports.com/rss/12040",                       # Sky Sports Football
    "https://www.espn.com/espn/rss/soccer/news",                 # ESPN Soccer
    "https://www.goal.com/feeds/en/news",                        # Goal.com
    "https://www.90min.com/rss",                                  # 90min
    "https://www.football365.com/feed",                           # Football365
    "https://www.uefa.com/rssfeed/news/",                        # UEFA (WC qualifying)
]

# YouTube — only analysis/news channels; avoid channels that post historical throwbacks
# FIFA Official (UCpcTrCXblq78GZrTUTLWeBw) deliberately excluded — mostly classic clips
YOUTUBE_CHANNEL_IDS: list[str] = [
    "UCGYYNGmyhZ_kwBF_lqqXdAQ",  # Tifo Football — tactical/news analysis
    "UCS9uQI-jC3DE0L4IpXyvr6w",  # ESPN FC — current football news
    "UCNAf1k0yIjyGu3k9BwAg3lg",  # Sky Sports Football — live news
    "UCiWLfSweyRNmLpgEHekhoAg",  # The Athletic Football — in-depth analysis
]

# X accounts — top football journalists + official tournament accounts
TRACKED_X_ACCOUNTS: list[str] = [
    "FabrizioRomano",    # transfers & squad news
    "OptaJoe",           # live stats & records
    "FIFAWorldCup",      # official tournament account
    "goal",              # breaking football news
    "ESPNFC",            # US-based WC coverage
    "SkySportsFOOTBALL", # UK football news
    "BBCSport",          # BBC football news
    "TheAthleticFC",     # premium analysis
    "transfermarkt",     # squad values & stats
    "FIFAcom",           # FIFA official updates
    "SquawkaNews",       # stats & match data
]

NITTER_INSTANCES: list[str] = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.catsarch.com",
    "https://nitter.unixfox.eu",
    "https://nitter.it",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# How far back to look per source type.
MAX_AGE_HOURS         = float(os.environ.get("MAX_CONTENT_AGE_HOURS", "6"))
YOUTUBE_MAX_AGE_HOURS = float(os.environ.get("YOUTUBE_MAX_AGE_HOURS", "24"))
NITTER_MAX_AGE_HOURS  = float(os.environ.get("NITTER_MAX_AGE_HOURS", "6"))

# Max items pulled per source per run — feeds are newest-first so this = latest N only
MAX_ITEMS_NEWS    = int(os.environ.get("MAX_ITEMS_NEWS", "5"))
MAX_ITEMS_NITTER  = int(os.environ.get("MAX_ITEMS_NITTER", "8"))
MAX_ITEMS_YOUTUBE = int(os.environ.get("MAX_ITEMS_YOUTUBE", "3"))

# Max chars of transcript to pass as content context
TRANSCRIPT_MAX_CHARS = int(os.environ.get("TRANSCRIPT_MAX_CHARS", "2000"))

# Append extras from env
for _f in os.environ.get("EXTRA_NEWS_FEEDS", "").split(","):
    if _f.strip():
        NEWS_FEEDS.append(_f.strip())
for _h in os.environ.get("EXTRA_X_ACCOUNTS", "").split(","):
    if _h.strip():
        TRACKED_X_ACCOUNTS.append(_h.strip().lstrip("@"))
for _c in os.environ.get("EXTRA_YOUTUBE_CHANNELS", "").split(","):
    if _c.strip():
        YOUTUBE_CHANNEL_IDS.append(_c.strip())


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

ARTICLE_BODY_MAX_CHARS = int(os.environ.get("ARTICLE_BODY_MAX_CHARS", "3000"))
ARTICLE_MIN_SUMMARY_CHARS = 200  # below this, we attempt to fetch article body


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _fetch_article_body(url: str) -> str:
    """Fetch and extract main article text via trafilatura. Returns '' on failure."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if not text:
            return ""
        return text[:ARTICLE_BODY_MAX_CHARS]
    except Exception as e:
        log.debug(f"Article fetch failed {url[:60]}: {e}")
        return ""


async def _enrich_with_article(item: dict) -> dict:
    """Replace thin RSS summary with scraped article body if possible."""
    if len(item.get("summary", "")) >= ARTICLE_MIN_SUMMARY_CHARS:
        return item  # summary already has enough content
    url = item.get("url", "")
    if not url:
        return item
    loop = asyncio.get_event_loop()
    async with _FETCH_SEM:
        body = await loop.run_in_executor(None, _fetch_article_body, url)
    if body:
        item["summary"] = body
        item["has_article_body"] = True
        log.debug(f"Article body fetched ({len(body)} chars): {item['title'][:60]}")
    return item


def _parse_feed(
    url: str,
    max_age_hours: float = MAX_AGE_HOURS,
    max_items: int = MAX_ITEMS_NEWS,
) -> list[dict]:
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Beteye/1.0"})
        if not feed.entries:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        items = []
        # Entries are newest-first; stop early once we have enough or hit the age cutoff
        for entry in feed.entries:
            if len(items) >= max_items:
                break
            pub = entry.get("published_parsed")
            if pub:
                try:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        break  # entries are chronological — nothing older is useful
                except Exception:
                    pass
            title = entry.get("title", "").strip()
            summary = _strip_html(
                entry.get("summary", entry.get("description", ""))
            )[:600]
            url_entry = entry.get("link", "")
            if not title or not url_entry:
                continue
            items.append({
                "title": title,
                "summary": summary,
                "url": url_entry,
                "source": feed.feed.get("title", url),
            })
        return items
    except Exception as e:
        log.warning(f"Feed parse failed {url[:60]}: {e}")
        return []


# Limit concurrent blocking calls into the thread pool so we don't saturate it
# and block the event loop. 8 concurrent feed fetches is plenty.
_FETCH_SEM = asyncio.Semaphore(8)


async def _async_parse(
    url: str,
    max_age_hours: float = MAX_AGE_HOURS,
    max_items: int = MAX_ITEMS_NEWS,
) -> list[dict]:
    async with _FETCH_SEM:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _parse_feed, url, max_age_hours, max_items)


# ---------------------------------------------------------------------------
# YouTube transcript enrichment
# ---------------------------------------------------------------------------

def _extract_video_id(url: str) -> str | None:
    """Extract video ID from a youtube.com/watch?v= or youtu.be/ URL."""
    try:
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            return parse_qs(parsed.query).get("v", [None])[0]
        if "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/")
    except Exception:
        pass
    return None


def _fetch_transcript(video_id: str) -> str:
    """
    Fetch auto-generated or manual captions and return them as plain text.
    Returns empty string if captions are unavailable (live streams, blocked, etc).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        segments = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "en-US", "en-GB"]
        )
        text = " ".join(s["text"] for s in segments)
        # Clean auto-generated artifacts like [Music] [Applause]
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:TRANSCRIPT_MAX_CHARS]
    except Exception:
        return ""


async def _enrich_with_transcript(item: dict) -> dict:
    """Try to replace the RSS description with the actual video transcript."""
    video_id = _extract_video_id(item["url"])
    if not video_id:
        return item

    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(None, _fetch_transcript, video_id)

    if transcript:
        item["summary"] = transcript
        item["has_transcript"] = True
        log.debug(f"Transcript fetched for {video_id} ({len(transcript)} chars)")
    else:
        log.debug(f"No transcript for {video_id} — using description")

    return item


def _youtube_rss(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


async def _fetch_youtube_channel(channel_id: str) -> list[dict]:
    """Fetch RSS items then enrich each video with its transcript."""
    items = await _async_parse(
        _youtube_rss(channel_id),
        max_age_hours=YOUTUBE_MAX_AGE_HOURS,
        max_items=MAX_ITEMS_YOUTUBE,
    )
    if not items:
        return []
    # Fetch transcripts concurrently across all videos in this channel
    enriched = await asyncio.gather(
        *[_enrich_with_transcript(item) for item in items],
        return_exceptions=True,
    )
    return [i for i in enriched if isinstance(i, dict)]


# ---------------------------------------------------------------------------
# Nitter RSS (X account tracking)
# ---------------------------------------------------------------------------

def _extract_tweet_id(url: str) -> str | None:
    """Extract numeric tweet ID from a Nitter status URL."""
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def _is_source_tweet(item: dict, handle: str) -> bool:
    """
    Return True only if this is an original tweet from the account, not a reply
    to a third-party conversation.
    Nitter marks replies as "R to @handle: ..." in the title.
    Also reject retweets (title starts with "RT by").
    """
    title = item.get("title", "")
    if title.startswith("R to @"):
        return False
    if title.startswith("RT by"):
        return False
    # URL must contain the tracked handle (not someone else's status they replied under)
    url = item.get("url", "").lower()
    if handle.lower() not in url:
        return False
    return True


async def _fetch_nitter(handle: str) -> list[dict]:
    for instance in NITTER_INSTANCES:
        raw = await _async_parse(
            f"{instance}/{handle}/rss",
            max_age_hours=NITTER_MAX_AGE_HOURS,
            max_items=MAX_ITEMS_NITTER,
        )
        if raw is None:
            log.debug(f"@{handle}: {instance} — parse error")
            continue
        if not raw:
            log.debug(f"@{handle}: {instance} — reachable but 0 items in last {NITTER_MAX_AGE_HOURS:.0f}h")
            # Still a working instance — return empty rather than trying others that serve same data
            return []

        items = []
        skipped = 0
        for item in raw:
            if not _is_source_tweet(item, handle):
                skipped += 1
                continue
            item["source"]       = f"@{handle}"
            item["tweet_id"]     = _extract_tweet_id(item.get("url", ""))
            item["source_bonus"] = 1
            if not item["summary"]:
                item["summary"] = item["title"]
            items.append(item)

        log.info(f"@{handle}: {len(items)} tweets ({skipped} replies/RTs filtered) via {instance}")
        return items

    log.warning(f"@{handle}: all {len(NITTER_INSTANCES)} Nitter instances unreachable")
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_all_items() -> list[dict]:
    """Fetch and deduplicate items from all sources."""
    tasks = (
        [_async_parse(url) for url in NEWS_FEEDS]
        + [_fetch_youtube_channel(cid) for cid in YOUTUBE_CHANNEL_IDS]
        + [_fetch_nitter(h) for h in TRACKED_X_ACCOUNTS]
    )
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    news_items: list[dict] = []
    yt_items:   list[dict] = []
    x_items:    list[dict] = []
    n_feeds = len(NEWS_FEEDS)
    n_yt    = len(YOUTUBE_CHANNEL_IDS)

    for idx, r in enumerate(results):
        if not isinstance(r, list):
            continue
        for item in r:
            url = item.get("url", "")
            if not url or url in seen_urls or not item.get("title"):
                continue
            seen_urls.add(url)
            if idx < n_feeds:
                news_items.append(item)
            elif idx < n_feeds + n_yt:
                yt_items.append(item)
            else:
                x_items.append(item)

    # Enrich thin news RSS summaries with actual article body text
    thin = [i for i in news_items if len(i.get("summary", "")) < ARTICLE_MIN_SUMMARY_CHARS]
    if thin:
        log.info(f"Fetching article bodies for {len(thin)} thin-summary news items…")
        enriched = await asyncio.gather(
            *[_enrich_with_article(i) for i in thin],
            return_exceptions=True,
        )
        enriched_map = {i["url"]: i for i in enriched if isinstance(i, dict)}
        news_items = [enriched_map.get(i["url"], i) for i in news_items]

    items = news_items + yt_items + x_items
    art = sum(1 for i in news_items if i.get("has_article_body"))
    yt  = sum(1 for i in yt_items  if i.get("has_transcript"))
    log.info(
        f"Fetched {len(items)} unique items — "
        f"news RSS: {len(news_items)} ({art} with article body) | "
        f"YouTube: {len(yt_items)} ({yt} with transcripts) | "
        f"X accounts: {len(x_items)}"
    )
    return items
