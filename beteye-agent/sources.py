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
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# How far back to look per collection run — tight since collector runs every 30 min.
# 2h buffer handles feeds that are slow to update.
MAX_AGE_HOURS = float(os.environ.get("MAX_CONTENT_AGE_HOURS", "2"))

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

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_feed(url: str) -> list[dict]:
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Beteye/1.0"})
        cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
        items = []
        for entry in feed.entries:
            pub = entry.get("published_parsed")
            if pub:
                try:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass
            title = entry.get("title", "").strip()
            summary = _strip_html(
                entry.get("summary", entry.get("description", ""))
            )[:400]
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


async def _async_parse(url: str) -> list[dict]:
    async with _FETCH_SEM:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _parse_feed, url)


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
    items = await _async_parse(_youtube_rss(channel_id))
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


async def _fetch_nitter(handle: str) -> list[dict]:
    for instance in NITTER_INSTANCES:
        items = await _async_parse(f"{instance}/{handle}/rss")
        if items:
            for item in items:
                item["source"]   = f"@{handle}"
                item["tweet_id"] = _extract_tweet_id(item.get("url", ""))
                if not item["summary"]:
                    item["summary"] = item["title"]
            log.debug(f"@{handle}: {len(items)} posts via {instance}")
            return items
    log.debug(f"@{handle}: all Nitter instances failed")
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
    items: list[dict] = []
    for r in results:
        if not isinstance(r, list):
            continue
        for item in r:
            url = item.get("url", "")
            if url and url not in seen_urls and item.get("title"):
                seen_urls.add(url)
                items.append(item)

    yt = sum(1 for i in items if i.get("has_transcript"))
    log.info(f"Fetched {len(items)} unique items ({yt} with video transcripts)")
    return items
