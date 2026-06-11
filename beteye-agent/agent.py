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
POST_INTERVAL_SECS    = int(os.environ.get("POST_INTERVAL_SECS", "180"))  # gap between posts in a run

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
MIN_ITEM_SCORE = int(os.environ.get("MIN_ITEM_SCORE", "3"))

# Must contain at least one of these to even be considered — prevents generic football noise
WC_CORE_TERMS = {
    "world cup", "worldcup", "wc2026", "2026 world cup", "world cup 2026",
    "usa 2026", "canada 2026", "mexico 2026",
    "group stage", "knockout stage", "quarterfinal", "semifinal",
    "team sheet", "starting xi", "squad list",
    "metlife", "sofi stadium", "azteca", "at&t stadium", "levi's stadium",
    "fifaworldcup", "fifa world cup",
}

# Reject outright if these appear without a WC core term — club/domestic league noise
NON_WC_BLOCKLIST = {
    "nwsl", "premier league", "champions league", "europa league",
    "conference league", "la liga", "serie a", "bundesliga", "ligue 1",
    "fa cup", "efl cup", "carabao cup", "copa del rey", "coppa italia",
    "women's super league", " wsl ", "women's champions league",
    "wave fc", "man city", "man utd", "manchester united", "manchester city",
    "arsenal", "chelsea", "liverpool", "tottenham", "newcastle",
    "real madrid", "barcelona", "atletico", "juventus", "inter milan", "ac milan",
    "psg", "paris saint-germain", "bayern munich", "borussia dortmund",
}

WC_KEYWORDS = {
    "world cup 2026": 5, "wc2026": 5, "2026 world cup": 5,
    "usa 2026": 4, "canada 2026": 4, "mexico 2026": 4,
    "metlife": 3, "sofi stadium": 3, "azteca": 3,
    "world cup": 3, "worldcup": 3,
    "group stage": 3, "knockout": 3, "quarterfinal": 3, "semifinal": 3,
    "qualify": 2, "qualifier": 2, "qualification": 2,
    "squad": 2, "team sheet": 3, "starting xi": 3, "lineup": 2,
    "injury": 2, "injury doubt": 3, "ruled out": 3, "fit for": 3,
    "suspended": 2, "red card": 2,
    "record": 2, "all-time": 2,
    "preview": 2, "prediction": 2, "odds": 2,
    "national team": 2, "international break": 2,
    "hat-trick": 2, "var": 2, "penalty": 2,
    "fifa": 1,
}

_HIST_YEAR_RE = re.compile(r'\b(19\d{2}|200\d|201\d|202[0-3])\b')


def _has_wc_signal(item: dict) -> bool:
    """Item must contain at least one core WC term. Reject if it's clearly club/domestic content."""
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()

    has_core = any(t in text for t in WC_CORE_TERMS)
    has_block = any(t in text for t in NON_WC_BLOCKLIST)

    if has_block and not has_core:
        return False
    return has_core

BANNED_PHRASES = (
    "game-changer, game changer, double high-five, let that sink in, buckle up, "
    "this is huge, groundbreaking, revolutionary, it's no secret, dive into, delve into, "
    "in a world where, at the end of the day, moving the needle, it's worth noting, "
    "make no mistake, what a time to be alive, truly remarkable, I cannot stress enough, "
    "think about that for a second, rest assured, needless to say, without further ado, "
    "it's important to note, football is more than a sport, "
    "under the radar, tip the scale, shift the dynamics, remains to be seen, "
    "one to watch, ones to watch, key player, unsung talent, unsung hero, "
    "could be crucial, might just, spotlight is on, all eyes on, dynamics of, "
    "narrative, storyline, fascinating, intriguing, captivating, compelling, "
    "football world, football fans, the beautiful game"
)

# ---------------------------------------------------------------------------
# Content-type modes — each post run cycles through these for variety
# ---------------------------------------------------------------------------
POST_MODES = ["news", "stat", "take"]

# Per-mode character limits — X Premium Basic allows 4,000 chars
MODE_CHAR_LIMITS = {
    "news":  1000,   # full story + context + CTA, no mid-sentence cuts
    "stat":   800,   # number + full context + CTA
    "take":  2000,   # proper opinion piece with evidence
    "list":  4000,   # full ranked list with reasons, closing statement
    "reply":  280,   # replies stay short — you're in someone else's thread
}

# Detect list/ranking articles that deserve a long-form treatment
_LIST_TITLE_RE = re.compile(
    r'\b(top \d+|ranking|ranked|power rank|best \d+|\d+ (players|countries|teams|things|reasons)|'
    r'who to watch|ones to watch|contenders|favourites|favorites|predictions|picks)\b',
    re.IGNORECASE,
)

MODE_INSTRUCTIONS = {
    "news": (
        "TASK — NEWS FLASH\n"
        "Report the core fact as original insight. DO NOT name any media outlet.\n\n"
        "FORMAT RULES (non-negotiable):\n"
        "- Each sentence on its own line\n"
        "- One blank line between each section\n"
        "- Section 1: the fact (1-2 lines)\n"
        "- Section 2: why it matters / what changes (1-2 lines)\n"
        "- Section 3: CTA tied to this specific story (1 line)\n\n"
        "EXAMPLE OUTPUT:\n"
        "Germany's players are funding bus transport for 600 fans from New York to New Jersey.\n\n"
        "Train fares were hiked 300% for the tournament. The squad stepped in and covered the cost themselves.\n\n"
        "Follow @beteye for everything happening off the pitch at WC 2026.\n\n"
        "Max 900 chars."
    ),
    "stat": (
        "TASK — STAT DROP\n"
        "Lead with one number. Make it land. DO NOT credit any source.\n\n"
        "FORMAT RULES (non-negotiable):\n"
        "- Each sentence on its own line\n"
        "- One blank line between each section\n"
        "- Section 1: the stat alone (1 line — short and punchy)\n"
        "- Section 2: context that makes the number hit harder (1-2 lines)\n"
        "- Section 3: CTA tied to this stat (1 line)\n\n"
        "EXAMPLE OUTPUT:\n"
        "80% of World Cup knockout goals came from set-piece patterns.\n\n"
        "Miss these signals, and you miss the game.\n"
        "Structural intelligence is the real edge.\n\n"
        "Follow @beteye for the numbers that define WC 2026.\n\n"
        "Max 700 chars."
    ),
    "take": (
        "TASK — SHARP TAKE\n"
        "State a confident original opinion grounded in a fact from the article. "
        "DO NOT credit any outlet. No 'according to', no 'reports say'.\n\n"
        "FORMAT RULES (non-negotiable):\n"
        "- Each sentence on its own line\n"
        "- One blank line between each section\n"
        "- Section 1: the take — bold declarative statement (1-2 lines)\n"
        "- Section 2: the evidence that backs it up (1-2 lines)\n"
        "- Section 3: CTA that invites a reply or action (1 line)\n\n"
        "EXAMPLE OUTPUT:\n"
        "The noise is everywhere.\n\n"
        "Group A is already decided on paper — the real battle is who finishes second.\n"
        "Three teams within 2 points on goal difference after matchday 1.\n\n"
        "Drop your Group A prediction below.\n\n"
        "Max 1800 chars."
    ),
    "list": (
        "TASK — ORIGINAL LIST POST\n"
        "The source is a ranking or list. Write your OWN curated version using facts from it. "
        "DO NOT credit the outlet.\n\n"
        "FORMAT RULES (non-negotiable):\n"
        "- Hook: 1 punchy line in ALL CAPS\n"
        "- One blank line\n"
        "- Numbered items, each on its own line: [Name or concept] — [specific fact]\n"
        "- One blank line after the list\n"
        "- Closing: 1 strong statement or CTA related to the topic\n\n"
        "EXAMPLE OUTPUT:\n"
        "5 TEAMS THAT WILL DEFINE WC 2026:\n\n"
        "1. France — Mbappé + Dembélé in peak form. Deepest attack in the tournament.\n"
        "2. Brazil — Vinícius Jr. leads a squad with 8 Champions League finalists.\n"
        "3. England — Bellingham anchors a midfield with genuine world-class depth.\n"
        "4. Spain — Lamine Yamal, 17, starts. The youngest squad at the tournament.\n"
        "5. Argentina — Defending champions. Messi's last World Cup. Built for this.\n\n"
        "Follow @beteye — we cover every match as it happens.\n\n"
        "Max 4000 chars."
    ),
    "reply": (
        "TASK — REPLY\n"
        "Add one fact or stat the original tweet missed. One sentence. Direct. No CTA. Max 180 chars."
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
    text  = (item.get("title", "") + " " + item.get("summary", "")).lower()
    score = sum(w for kw, w in WC_KEYWORDS.items() if kw in text)
    return score + item.get("source_bonus", 0)


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


def _select_mode(item: dict, is_breaking: bool, post_index: int) -> str:
    """
    Choose content mode. List/ranking articles always get 'list' mode.
    Breaking news always gets 'news'. Otherwise use learned performance weights.
    """
    if is_breaking:
        return "news"

    # Detect list/ranking articles — give them a richer long-form treatment
    if _LIST_TITLE_RE.search(item.get("title", "")):
        return "list"

    intel = _load_intelligence()
    mode_perf: dict = intel.get("mode_performance", {})

    if mode_perf:
        weights = [max(mode_perf.get(m, 1.0), 0.1) for m in POST_MODES]
        return random.choices(POST_MODES, weights=weights, k=1)[0]

    return POST_MODES[post_index % len(POST_MODES)]


async def _generate_post(item: dict, mode: str = "news") -> str | None:
    today       = datetime.now(timezone.utc).strftime("%B %d, %Y")
    pub_approx  = item.get("collected_at", "")[:10]
    angle       = random.choice(ANGLES)
    instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["news"])
    char_limit  = MODE_CHAR_LIMITS.get(mode, 280)

    # Inject learned intelligence
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
        f"SOURCE: {item.get('source', 'unknown')} (do NOT mention this outlet in the post)\n"
        f"DATE COLLECTED: ~{pub_approx}  |  TODAY: {today}\n\n"
        f"ARTICLE CONTENT:\n{item.get('summary', '(no body — use headline only)')}\n\n"
        f"---\n"
        f"SECONDARY ANGLE: {angle}\n\n"
        f"{instruction}"
        f"{learned_block}\n\n"
        f"HARD RULES:\n"
        f"- Only state facts from ARTICLE CONTENT. Do NOT add context from training data.\n"
        f"- NEVER mention any media outlet, website, or publication name.\n"
        f"- Be specific — name a player, club, country, stadium, number, or event. Never be vague ('a key player', 'some teams', 'certain matches').\n"
        f"- Never say 'today', 'yesterday', 'this morning' unless ARTICLE CONTENT says so.\n"
        f"- Do not start with 'I'.\n"
        f"- BANNED PHRASES (never use these): {BANNED_PHRASES}"
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
        if not results:
            return None
        text = results[0]["content"].strip()

    return text[:char_limit]


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
    skipped_offtopic = 0
    has_breaking  = False

    for item in items:
        key = _item_key(item)
        if key in seen_set or key in queued_keys:
            continue

        # Reject historical throwbacks
        if _HIST_YEAR_RE.search(item.get("title", "")):
            skipped_hist += 1
            continue

        # Hard gate — must have a World Cup 2026 signal, not just generic football
        if not _has_wc_signal(item):
            skipped_offtopic += 1
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
        f"skipped: {skipped_offtopic} off-topic, {skipped_hist} historical, {skipped_low} low-score | "
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

        mode = _select_mode(item=item, is_breaking=item.get("is_breaking", False), post_index=posted)

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

            if DRY_RUN:
                fake_id = f"dry_{int(datetime.now(timezone.utc).timestamp())}"
                log.info(f"[poster] [DRY RUN] [{mode}] ({len(text)} chars)\n{text}\n{'─'*60}")
                posted_id = fake_id
            else:
                posted_id = post_tweet(text, reply_to_id=tweet_id_to_reply)
                log.info(f"[poster] Posted {posted_id} [{mode}] ({len(text)} chars)\n{text}\n{'─'*60}")

            seen_set.add(item["key"])
            used_keys.append(item["key"])
            posted += 1

            # Pace posts — don't blast all N at once; wait between each (skip after last)
            if posted < POSTS_PER_RUN and POST_INTERVAL_SECS > 0:
                log.info(f"[poster] Waiting {POST_INTERVAL_SECS}s before next post…")
                await asyncio.sleep(POST_INTERVAL_SECS)

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
