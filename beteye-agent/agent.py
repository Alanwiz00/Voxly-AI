"""
Beteye — autonomous World Cup content agent.

Jobs:
  collect_job        — every N min (10 on match day, 30 off): fetch, filter, queue.
                       Triggers post_job immediately on breaking news or enough fresh items.
  post_job           — triggered from collect_job; also runs as fallback every 6h.
  check_performance  — every 6h: reads engagement metrics for tweets posted 6h+ ago.
"""
import asyncio
import hashlib
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from sources import get_all_items
from poster import post_tweet, get_tweet_metrics
from matchday import get_match_config, is_match_day

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [beteye] %(message)s",
)
log = logging.getLogger("beteye")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VOXLY_API_URL         = os.environ.get("VOXLY_API_URL", "http://backend:8000")
VOXLY_API_KEY         = os.environ["VOXLY_API_KEY"]
PERSONA_ID            = os.environ.get("PERSONA_ID")
POSTS_PER_RUN         = int(os.environ.get("POSTS_PER_RUN", "4"))
COLLECT_INTERVAL_MINS = float(os.environ.get("COLLECT_INTERVAL_MINS", "30"))
FALLBACK_POST_HOURS   = float(os.environ.get("FALLBACK_POST_HOURS", "4"))
MIN_QUEUE_THRESHOLD   = int(os.environ.get("MIN_QUEUE_THRESHOLD", "2"))
MIN_POST_GAP_MINS     = float(os.environ.get("MIN_POST_GAP_MINS", "45"))
BREAKING_SCORE        = int(os.environ.get("BREAKING_SCORE_THRESHOLD", "6"))
DRY_RUN               = os.environ.get("DRY_RUN", "false").lower() == "true"
ENABLE_REPLIES        = os.environ.get("ENABLE_REPLIES", "false").lower() == "true"

DATA_DIR     = Path("/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_FILE   = DATA_DIR / "queue.json"
SEEN_FILE    = DATA_DIR / "seen.json"
STATE_FILE   = DATA_DIR / "state.json"
PERF_FILE    = DATA_DIR / "performance.json"
INTEL_FILE   = DATA_DIR / "intelligence.json"  # learned green/red flags + mode weights

MIN_POSTS_FOR_ANALYSIS = int(os.environ.get("MIN_POSTS_FOR_ANALYSIS", "5"))

# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------
MIN_ITEM_SCORE = int(os.environ.get("MIN_ITEM_SCORE", "2"))

WC_KEYWORDS = {
    "world cup 2026": 5, "wc2026": 5, "2026 world cup": 5,
    "usa 2026": 4, "canada 2026": 4, "mexico 2026": 4,
    "metlife": 3, "sofi stadium": 3, "azteca": 3,
    "world cup": 3, "worldcup": 3,
    "group stage": 3, "knockout": 3, "quarterfinal": 3, "semifinal": 3, "final": 2,
    "qualify": 2, "qualifier": 2, "qualification": 2,
    "squad": 2, "team sheet": 3, "starting xi": 3, "lineup": 2,
    "injury": 2, "injury doubt": 3, "ruled out": 3, "fit for": 3,
    "suspended": 2, "red card": 2,
    "transfer": 1, "signing": 1,
    "record": 2, "all-time": 2,
    "preview": 2, "prediction": 2, "odds": 2,
    "national team": 2, "international": 1,
    "goal": 1, "assist": 1, "hat-trick": 3,
    "var": 2, "penalty": 2, "own goal": 2,
    "fifa": 1,
}

_HIST_YEAR_RE = re.compile(r'\b(19\d{2}|200\d|201\d|202[0-3])\b')

BANNED_PHRASES = (
    "game-changer, game changer, double high-five, let that sink in, buckle up, "
    "this is huge, groundbreaking, revolutionary, it's no secret, dive into, delve into, "
    "in a world where, at the end of the day, moving the needle, it's worth noting, "
    "make no mistake, what a time to be alive, truly remarkable, I cannot stress enough, "
    "think about that for a second, rest assured, needless to say, without further ado, "
    "it's important to note, football is more than a sport"
)

# ---------------------------------------------------------------------------
# Content-type modes — each post run cycles through these for variety
# ---------------------------------------------------------------------------
POST_MODES = ["news", "stat", "take"]

MODE_INSTRUCTIONS = {
    "news": (
        "TASK — NEWS FLASH: Write a tweet that reports the single most important fact from this story. "
        "Sentence 1: WHO did WHAT (name + action + number if available). "
        "Sentence 2: the concrete consequence — what changes now. "
        "No questions. No filler. Statement only. Max 220 chars."
    ),
    "stat": (
        "TASK — STAT DROP: Lead with ONE specific number from this story (goals, minutes, fee, ranking). "
        "Sentence 1: [NUMBER] [FACT] — make the number land hard. "
        "Sentence 2: why that number is significant in context. "
        "No questions. Declarative statements only. Max 220 chars."
    ),
    "take": (
        "TASK — SHARP TAKE: State a strong, confident opinion on this story in 1-2 sentences. "
        "Name players, clubs, or federations directly. Anchor the take in a specific fact from the article. "
        "No hedging words (perhaps, might, could). No questions. "
        "Conviction over conversation. Max 220 chars."
    ),
    "reply": (
        "TASK — REPLY: Add one concrete fact, stat, or piece of context that the original tweet missed. "
        "State it as a fact, not a question. Be direct. Max 200 chars."
    ),
}

ANGLES = [
    "The stat that proves it.",
    "What the mainstream media is missing.",
    "The tactical detail nobody's covering.",
    "The contrarian view — argue the opposite of the obvious take.",
    "Historical comparison from past World Cups.",
    "The player nobody's talking about who is affected most.",
    "What this means for the bracket right now.",
    "The bettor's angle — how does this shift the odds?",
    "Read between the lines — what is the federation NOT saying?",
    "The dark horse benefit nobody's mentioned.",
]

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _item_key(item: dict) -> str:
    raw = item.get("url") or item.get("title") or ""
    return hashlib.md5(raw.encode()).hexdigest()


def _score_item(item: dict) -> int:
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return sum(w for kw, w in WC_KEYWORDS.items() if kw in text)


def _minutes_since_last_post() -> float:
    state = _load_json(STATE_FILE, {})
    last = state.get("last_posted_at")
    if not last:
        return float("inf")
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
    except Exception:
        return float("inf")


def _mark_posted() -> None:
    state = _load_json(STATE_FILE, {})
    state["last_posted_at"] = datetime.now(timezone.utc).isoformat()
    _save_json(STATE_FILE, state)


# ---------------------------------------------------------------------------
# Generation — uses /generate/from-source to ground output in actual news
# ---------------------------------------------------------------------------

def _load_intelligence() -> dict:
    return _load_json(INTEL_FILE, {})


def _select_mode(is_breaking: bool, post_index: int) -> str:
    """
    Choose content mode weighted by learned performance.
    Breaking items always start with 'news'.
    """
    if is_breaking:
        return "news"

    intel = _load_intelligence()
    mode_perf: dict = intel.get("mode_performance", {})

    if mode_perf:
        # Weight by average engagement score — modes with higher scores get picked more often
        weights = [max(mode_perf.get(m, 1.0), 0.1) for m in POST_MODES]
        return random.choices(POST_MODES, weights=weights, k=1)[0]

    # No intelligence yet — simple round-robin
    return POST_MODES[post_index % len(POST_MODES)]


async def _generate_post(item: dict, mode: str = "news") -> str | None:
    today      = datetime.now(timezone.utc).strftime("%B %d, %Y")
    pub_approx = item.get("collected_at", "")[:10]
    angle      = random.choice(ANGLES)
    instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["news"])

    # Inject learned intelligence — green flags to amplify, red flags to avoid
    intel       = _load_intelligence()
    green_flags = intel.get("green_flags", [])
    red_flags   = intel.get("red_flags", [])
    best_hook   = intel.get("best_hook_pattern", "")

    learned_block = ""
    if green_flags or red_flags:
        parts = ["\n\nLEARNED FROM PAST PERFORMANCE (apply these):"]
        if best_hook:
            parts.append(f"BEST PERFORMING HOOK PATTERN: {best_hook}")
        if green_flags:
            parts.append("GREEN FLAGS — DO MORE OF:")
            parts.extend(f"  + {f}" for f in green_flags[:5])
        if red_flags:
            parts.append("RED FLAGS — NEVER DO:")
            parts.extend(f"  - {f}" for f in red_flags[:5])
        learned_block = "\n".join(parts)

    source_text = (
        f"HEADLINE: {item['title']}\n"
        f"SOURCE: {item.get('source', 'unknown')}\n"
        f"DATE COLLECTED: ~{pub_approx}  |  TODAY: {today}\n\n"
        f"ARTICLE CONTENT:\n{item.get('summary', '(no body — use headline only)')}\n\n"
        f"---\n"
        f"SECONDARY ANGLE: {angle}\n\n"
        f"{instruction}"
        f"{learned_block}\n\n"
        f"HARD RULES:\n"
        f"- Only state facts from ARTICLE CONTENT. Do NOT add context from training data.\n"
        f"- Never say 'today', 'yesterday', 'this morning' unless ARTICLE CONTENT says so.\n"
        f"- Do not start with 'I'.\n"
        f"- BANNED: {BANNED_PHRASES}"
    )

    form_data: dict = {
        "platform":     "twitter",
        "content_type": "idea",
        "idea_count":   "1",
        "text":         source_text,
    }
    if PERSONA_ID:
        form_data["persona_id"] = str(PERSONA_ID)

    async with httpx.AsyncClient(
        base_url=VOXLY_API_URL,
        headers={"Authorization": f"Bearer {VOXLY_API_KEY}"},
        timeout=90.0,
    ) as client:
        resp = await client.post("/generate/from-source", data=form_data)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0]["content"].strip() if results else None


# ---------------------------------------------------------------------------
# Job 1 — Collector
# ---------------------------------------------------------------------------

_current_collect_interval = COLLECT_INTERVAL_MINS


async def collect_job() -> None:
    global _current_collect_interval
    mc = get_match_config()

    # Dynamically adjust collection interval for match-day mode
    desired_mins = mc.get("collect_interval_mins") or COLLECT_INTERVAL_MINS
    if desired_mins != _current_collect_interval:
        scheduler.reschedule_job(
            "collector",
            trigger="interval",
            minutes=desired_mins,
            misfire_grace_time=300,
        )
        _current_collect_interval = desired_mins
        log.info(f"[collect] Interval → {desired_mins}min ({'match-day' if is_match_day() else 'normal'})")

    effective_threshold = mc.get("min_threshold") or MIN_QUEUE_THRESHOLD
    effective_gap       = mc.get("min_gap_mins")  or MIN_POST_GAP_MINS
    breaking_score      = mc.get("breaking_score") or BREAKING_SCORE

    log.info(f"[collect] Fetching — threshold={effective_threshold} gap={effective_gap}min breaking≥{breaking_score}")

    seen: list        = _load_json(SEEN_FILE, [])
    seen_set: set     = set(seen)
    queue: list[dict] = _load_json(QUEUE_FILE, [])
    queued_keys       = {i["key"] for i in queue}

    items = await get_all_items()
    added         = 0
    skipped_hist  = 0
    skipped_low   = 0
    has_breaking  = False

    for item in items:
        key = _item_key(item)
        if key in seen_set or key in queued_keys:
            continue

        # Reject historical throwbacks
        if _HIST_YEAR_RE.search(item.get("title", "")):
            skipped_hist += 1
            continue

        score = _score_item(item)

        if score < MIN_ITEM_SCORE:
            skipped_low += 1
            continue

        if score >= breaking_score:
            has_breaking = True

        queue.append({
            "key":            key,
            "title":          item["title"],
            "summary":        item.get("summary", ""),
            "url":            item.get("url", ""),
            "source":         item.get("source", ""),
            "tweet_id":       item.get("tweet_id"),
            "score":          score,
            "is_breaking":    score >= breaking_score,
            "has_transcript": item.get("has_transcript", False),
            "collected_at":   datetime.now(timezone.utc).isoformat(),
        })
        added += 1

    queue.sort(key=lambda x: (x.get("is_breaking", False), x.get("score", 0)), reverse=True)
    queue = queue[:300]
    _save_json(QUEUE_FILE, queue)

    log.info(
        f"[collect] +{added} queued | "
        f"skipped: {skipped_hist} historical, {skipped_low} low-relevance | "
        f"breaking: {has_breaking} | queue: {len(queue)}"
    )

    # --- Decide whether to post now ---
    gap = _minutes_since_last_post()

    if has_breaking:
        # Breaking news overrides the gap entirely
        log.info(f"[collect] BREAKING NEWS detected — posting immediately (gap was {gap:.0f}min)")
        await post_job()
    elif added >= effective_threshold:
        if gap >= effective_gap:
            log.info(f"[collect] {added} new items + gap OK ({gap:.0f}min) — posting now")
            await post_job()
        else:
            log.info(f"[collect] {added} new items but gap too short ({gap:.0f}/{effective_gap}min) — holding")
    else:
        log.info(f"[collect] Only {added} new items (threshold={effective_threshold}) — no post triggered")


# ---------------------------------------------------------------------------
# Job 2 — Poster
# ---------------------------------------------------------------------------

async def post_job() -> None:
    log.info("[poster] Starting post run…")
    queue: list[dict] = _load_json(QUEUE_FILE, [])
    seen: list        = _load_json(SEEN_FILE, [])
    seen_set          = set(seen)
    perf: list        = _load_json(PERF_FILE, [])

    if not queue:
        log.info("[poster] Queue empty — skipping")
        return

    posted    = 0
    used_keys: list[str] = []

    for i, item in enumerate(queue):
        if posted >= POSTS_PER_RUN:
            break

        mode = _select_mode(is_breaking=item.get("is_breaking", False), post_index=posted)

        # Determine if this should be posted as a reply
        tweet_id_to_reply = None
        if (
            ENABLE_REPLIES
            and item.get("tweet_id")
            and item.get("source", "").startswith("@")
            and item["score"] >= 4
        ):
            tweet_id_to_reply = item["tweet_id"]
            mode = "reply"

        is_reply = tweet_id_to_reply is not None
        log.info(
            f"[poster] [{mode.upper()}{'→reply' if is_reply else ''}] "
            f"[{item.get('source', '?')}]"
            f"{'[BREAKING]' if item.get('is_breaking') else ''}"
            f"{'[transcript]' if item.get('has_transcript') else ''}: "
            f"{item['title'][:70]}"
        )

        try:
            text = await _generate_post(item, mode=mode)
            if not text:
                log.warning("[poster] Empty generation — skipping")
                continue

            text = text[:280]

            if DRY_RUN:
                fake_id = f"dry_{int(datetime.now(timezone.utc).timestamp())}"
                log.info(f"[poster] [DRY RUN] [{mode}]\n{text}\n{'─'*60}")
                posted_id = fake_id
            else:
                posted_id = post_tweet(text, reply_to_id=tweet_id_to_reply)
                log.info(f"[poster] Posted {posted_id} [{mode}]: {text[:80]}…")

            seen_set.add(item["key"])
            used_keys.append(item["key"])
            posted += 1

            # Track for performance review in 6h
            perf.append({
                "tweet_id":    posted_id,
                "mode":        mode,
                "text":        text,        # actual tweet content — used for pattern analysis
                "is_reply":    is_reply,
                "is_breaking": item.get("is_breaking", False),
                "score":       item["score"],
                "title":       item["title"][:120],
                "source":      item.get("source", ""),
                "posted_at":   datetime.now(timezone.utc).isoformat(),
                "metrics":     None,
            })

        except httpx.HTTPStatusError as e:
            log.error(f"[poster] VoxlyAI {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            log.error(f"[poster] Error: {e}")

    queue = [i for i in queue if i["key"] not in used_keys]
    _save_json(QUEUE_FILE, queue)
    _save_json(SEEN_FILE, list(seen_set)[-5000:])
    _save_json(PERF_FILE, perf[-200:])

    if posted:
        _mark_posted()

    log.info(f"[poster] Done — {posted}/{POSTS_PER_RUN} posted | queue remaining: {len(queue)}")


# ---------------------------------------------------------------------------
# Job 3 — Performance tracker (runs every 6h)
# ---------------------------------------------------------------------------

async def check_performance() -> None:
    perf: list = _load_json(PERF_FILE, [])
    now        = datetime.now(timezone.utc)
    updated    = False

    for entry in perf:
        if entry.get("metrics"):
            continue  # already fetched
        if entry["tweet_id"].startswith("dry_"):
            continue  # dry run — no real tweet

        try:
            posted_at = datetime.fromisoformat(entry["posted_at"])
        except Exception:
            continue

        age_hours = (now - posted_at).total_seconds() / 3600
        if age_hours < 6:
            continue  # too soon

        metrics = get_tweet_metrics(entry["tweet_id"])
        if metrics:
            entry["metrics"] = metrics
            updated = True
            log.info(
                f"[perf] [{entry['mode']}] {entry['title'][:50]} → "
                f"impressions={metrics.get('impression_count', '?')} "
                f"likes={metrics.get('like_count', '?')} "
                f"rt={metrics.get('retweet_count', '?')}"
            )
        else:
            log.debug(f"[perf] No metrics yet for {entry['tweet_id']}")

    if updated:
        _save_json(PERF_FILE, perf)
        _log_performance_summary(perf)
        await _run_performance_analysis(perf)


async def _run_performance_analysis(perf: list) -> None:
    """Call /analyze/performance and persist results to intelligence.json."""
    with_metrics = [e for e in perf if e.get("metrics") and e.get("text")]
    if len(with_metrics) < MIN_POSTS_FOR_ANALYSIS:
        log.info(f"[perf] Only {len(with_metrics)} posts with metrics+text — need {MIN_POSTS_FOR_ANALYSIS} for analysis")
        return

    def _eng(e: dict) -> int:
        m = e["metrics"]
        return (
            m.get("impression_count", 0)
            + m.get("like_count", 0) * 10
            + m.get("retweet_count", 0) * 20
            + m.get("reply_count", 0) * 15
        )

    posts_payload = [
        {
            "text":        e["text"],
            "mode":        e["mode"],
            "impressions": e["metrics"].get("impression_count", 0),
            "likes":       e["metrics"].get("like_count", 0),
            "retweets":    e["metrics"].get("retweet_count", 0),
            "replies":     e["metrics"].get("reply_count", 0),
        }
        for e in with_metrics
    ]

    try:
        async with httpx.AsyncClient(
            base_url=VOXLY_API_URL,
            headers={"Authorization": f"Bearer {VOXLY_API_KEY}"},
            timeout=60.0,
        ) as client:
            resp = await client.post("/analyze/performance", json={"posts": posts_payload})
            resp.raise_for_status()
            result = resp.json()

        if "error" in result:
            log.warning(f"[perf] Analysis returned error: {result['error']}")
            return

        _save_json(INTEL_FILE, result)
        log.info(
            f"[perf] Intelligence updated | "
            f"green_flags={len(result.get('green_flags', []))} "
            f"red_flags={len(result.get('red_flags', []))} | "
            f"mode_performance={result.get('mode_performance', {})} | "
            f"insight: {result.get('insight', '')[:100]}"
        )
    except Exception as exc:
        log.error(f"[perf] Performance analysis failed: {exc}")


def _log_performance_summary(perf: list) -> None:
    """Log top and bottom performers to guide angle selection."""
    with_metrics = [e for e in perf if e.get("metrics")]
    if len(with_metrics) < 3:
        return

    def score(e):
        m = e["metrics"]
        return m.get("impression_count", 0) + m.get("like_count", 0) * 5 + m.get("retweet_count", 0) * 10

    ranked = sorted(with_metrics, key=score, reverse=True)
    log.info("[perf] Top performer: [%s] %s (score=%d)", ranked[0]["mode"], ranked[0]["title"][:60], score(ranked[0]))
    if len(ranked) > 1:
        log.info("[perf] Lowest performer: [%s] %s (score=%d)", ranked[-1]["mode"], ranked[-1]["title"][:60], score(ranked[-1]))

    # Mode breakdown
    from collections import defaultdict
    mode_scores: dict = defaultdict(list)
    for e in with_metrics:
        mode_scores[e["mode"]].append(score(e))
    for mode, scores in mode_scores.items():
        avg = sum(scores) / len(scores)
        log.info(f"[perf] Mode '{mode}': avg_score={avg:.0f} over {len(scores)} posts")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

scheduler: AsyncIOScheduler = None  # type: ignore[assignment]


async def main() -> None:
    global scheduler

    mc = get_match_config()
    initial_collect_mins = mc.get("collect_interval_mins") or COLLECT_INTERVAL_MINS

    log.info(
        f"Beteye starting | "
        f"collect={initial_collect_mins}min | "
        f"threshold={MIN_QUEUE_THRESHOLD} items | gap={MIN_POST_GAP_MINS}min | "
        f"breaking_score≥{BREAKING_SCORE} | posts_per_run={POSTS_PER_RUN} | "
        f"replies={'on' if ENABLE_REPLIES else 'off'} | dry_run={DRY_RUN}"
    )
    if not PERSONA_ID:
        log.warning("PERSONA_ID not set — run setup.py first")

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        collect_job,
        trigger="interval",
        minutes=initial_collect_mins,
        next_run_time=datetime.now(timezone.utc),
        id="collector",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        post_job,
        trigger="interval",
        hours=FALLBACK_POST_HOURS,
        next_run_time=datetime.now(timezone.utc) + timedelta(hours=FALLBACK_POST_HOURS),
        id="poster_fallback",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )

    scheduler.add_job(
        check_performance,
        trigger="interval",
        hours=6,
        next_run_time=datetime.now(timezone.utc) + timedelta(hours=6),
        id="perf_check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    log.info(f"Collector fires now. Fallback poster in {FALLBACK_POST_HOURS}h. Perf check in 6h.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Beteye stopped")


if __name__ == "__main__":
    asyncio.run(main())
