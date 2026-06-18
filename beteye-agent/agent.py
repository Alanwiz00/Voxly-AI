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
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from sources import get_all_items
import tweepy
from poster import post_tweet, get_tweet_metrics, upload_media, validate_credentials
from image_gen import generate_post_image
from matchday import get_match_config, is_match_day
from wc_fixtures import (get_fixture_context_block, fixture_count_today,
                         ensure_schedule_fresh, get_todays_fixtures,
                         fetch_todays_fixtures_live)
from post_schedule import PostSlot, build_daily_schedule, describe_schedule, MODE_DAILY_CAPS

ET = ZoneInfo("America/New_York")

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
POSTS_PER_RUN         = int(os.environ.get("POSTS_PER_RUN", "1"))
DAILY_POST_MAX        = int(os.environ.get("DAILY_POST_MAX", "20"))
COLLECT_INTERVAL_MINS = float(os.environ.get("COLLECT_INTERVAL_MINS", "30"))
STARTUP_GRACE_MINS    = float(os.environ.get("STARTUP_GRACE_MINS", "30"))
QUEUE_MAX_AGE_HOURS   = float(os.environ.get("QUEUE_MAX_AGE_HOURS", "2"))
BREAKING_SCORE        = int(os.environ.get("BREAKING_SCORE_THRESHOLD", "6"))
BREAKING_DAILY_CAP    = int(os.environ.get("BREAKING_DAILY_CAP", "3"))
BREAKING_MIN_GAP_MINS = int(os.environ.get("BREAKING_MIN_GAP_MINS", "60"))
DRY_RUN               = os.environ.get("DRY_RUN", "false").lower() == "true"
ENABLE_REPLIES        = os.environ.get("ENABLE_REPLIES", "false").lower() == "true"
POST_INTERVAL_SECS    = int(os.environ.get("POST_INTERVAL_SECS", "180"))

DATA_DIR     = Path("/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

_AGENT_START_TIME = datetime.now(timezone.utc)  # used to enforce startup grace period
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
    "game-changer, game changer, double high-five, double high fives, let that sink in, buckle up, "
    "this is huge, groundbreaking, revolutionary, it's no secret, dive into, delve into, "
    "in a world where, at the end of the day, moving the needle, it's worth noting, "
    "make no mistake, what a time to be alive, truly remarkable, I cannot stress enough, "
    "think about that for a second, rest assured, needless to say, without further ado, "
    "it's important to note, football is more than a sport, "
    "under the radar, tip the scale, shift the dynamics, remains to be seen, "
    "one to watch, ones to watch, key player, unsung talent, unsung hero, "
    "could be crucial, might just, spotlight is on, all eyes on, dynamics of, "
    "narrative, storyline, fascinating, intriguing, captivating, compelling, "
    "football world, football fans, the beautiful game, "
    "no small feat, it goes without saying, it's fair to say, safe to say, "
    "one thing is clear, it's clear that, speaks volumes, level up, hit different, "
    "on another level, more than just, more than a game, more than a match, "
    "this is not just, it's not just, a testament to, testament to their, "
    "electric atmosphere, packed stadium, roaring crowd, fever pitch, "
    "pride of a nation, moment of the tournament, history books, rewrite history, "
    "seize the moment, rise to the occasion, the stage is set"
)

# ---------------------------------------------------------------------------
# Content-type modes
# ---------------------------------------------------------------------------
POST_MODES = ["news", "stat", "take", "matchday"]
# Default weights — lean heavily on take + matchday, less raw news
POST_MODE_DEFAULT_WEIGHTS = [1, 2, 3, 2]  # news:stat:take:matchday

# Hard Twitter post limit — 280 for standard accounts, up to 4000 for X Premium.
# Set TWITTER_CHAR_LIMIT in .env to increase once the account is on X Premium.
TWITTER_CHAR_LIMIT = int(os.environ.get("TWITTER_CHAR_LIMIT", "270"))

# Per-mode character limits — model generates up to this much content.
# Must not exceed TWITTER_CHAR_LIMIT; these act as a style guide, not a hard cap.
MODE_CHAR_LIMITS = {
    "news":     TWITTER_CHAR_LIMIT,
    "stat":     TWITTER_CHAR_LIMIT,
    "take":     TWITTER_CHAR_LIMIT,
    "breaking": TWITTER_CHAR_LIMIT,
    "matchday": TWITTER_CHAR_LIMIT,
    "list":     TWITTER_CHAR_LIMIT,
    "reply":    min(TWITTER_CHAR_LIMIT, 270),
}

# Detect list/ranking articles that deserve a long-form treatment
_LIST_TITLE_RE = re.compile(
    r'\b(top \d+|ranking|ranked|power rank|best \d+|\d+ (players|countries|teams|things|reasons)|'
    r'who to watch|ones to watch|contenders|favourites|favorites|predictions|picks)\b',
    re.IGNORECASE,
)

# CLOSING LINE GUIDE — one per post, injected into every mode instruction
_CLOSING_LINE_GUIDE = """\
CLOSING LINE — pick exactly ONE for the final line of the post:
  • Question  (engagement): "What are your predictions?" / "Who wins tonight?" / "Drop your pick below 👇"
  • Directive (action):     "Drop it below 👇" / "Retweet if you agree." / "Tag someone watching tonight."
  • Brand stamp:            "@BetEye 👁" / "Follow @beteye for more on this." / "That someone is @BetEye. 👁"
  • Bold statement:         A punchy one-liner that lands on its own — no action needed.
RULE: Exactly ONE closing line. At most ONE question mark in the entire post.\
"""

MODE_INSTRUCTIONS = {

    "stat": (
        "TASK — STAT DROP\n"
        "Lead with ONE hard number from the article. Build from there.\n\n"
        "VOICE:\n"
        "  Short sentences. Each one lands on its own line.\n"
        "  Stack 2–4 stats or facts that make the lead number hit harder.\n"
        "  Staccato fragments are good for contrast: 'Not Mbappé. Not Neymar. Not Ibrahimović.'\n"
        "  Understated confidence — don't oversell. Let the number speak.\n"
        "  If a player or team is involved in TODAY'S FIXTURES, tie it to that match: 'Tonight he's at [city].'\n\n"
        "FORMAT (each section separated by a blank line):\n"
        "  [The stat — ONE line, specific number, no source name]\n\n"
        "  [1–2 lines of context / scale / why it matters]\n\n"
        "  [Optional staccato contrast: 'Not X. Not Y. Not Z.']\n\n"
        "  [If relevant: tie to today's match or current tournament moment]\n\n"
        + _CLOSING_LINE_GUIDE +
        "\n\nEXAMPLE OUTPUT:\n"
        "Kvaratskhelia has scored in 4 straight UCL knockout games.\n\n"
        "No PSG player has ever done that.\n"
        "Not Mbappé. Not Neymar. Not Ibrahimović.\n\n"
        "This guy just walked into that conversation quietly.\n\n"
        "Tonight he's at Anfield.\n"
        "What market are you betting?\n\n"
        "Drop it below 👇\n\n"
        "Max 260 chars."
    ),

    "breaking": (
        "TASK — POST-MATCH BREAKING REPORT (FEATURED FIXTURE only)\n"
        "1 hour has passed since this match ended. You have collected articles, stats, and reactions.\n"
        "Write a comprehensive post-match intelligence report — specific, sharp, no fluff.\n\n"
        "⚠ FORMAT — NON-NEGOTIABLE: Every sentence/paragraph on its own line, separated by a blank line.\n\n"
        "STRUCTURE:\n"
        "  Line 1: MATCH TITLE in ALL CAPS — e.g. 'FRANCE 2 – 0 SENEGAL'\n"
        "           Use ONLY the VERIFIED SCORE from context. Never guess.\n"
        "  Line 2–3: The story in 2 lines. What decided it. Key moment or player.\n"
        "  Line 4–5: The numbers — stats, records, historical context that make this result bigger.\n"
        "  Line 6: Group table implication — what this means for Group X standings.\n"
        "  Line 7: One player spotlight — who showed up or bottled it.\n"
        "  Line 8: BetEye intelligence angle — what the data said before the match that now makes sense.\n"
        "           End with @BetEye_ 👁. Never use the stock phrase.\n"
        "  Line 9: Closing — where does this team go from here. Bold, no question mark.\n\n"
        "RULES:\n"
        "- FEATURED FIXTURE only. One match. Nothing else.\n"
        "- Use the VERIFIED SCORE — do NOT invent any goal numbers.\n"
        "- STATS: Only use numbers (minutes, career tallies, caps, percentages) that are EXPLICITLY in the article content. "
        "If a stat is not in the source text, leave it out. Never fill gaps from memory.\n"
        "- GOAL FRAMING: Never call a goal a 'winner', 'late winner', 'equaliser', or 'opener' unless the source says so. "
        "State what the scoreline was when it went in (e.g. 'made it 3-2') — that is enough.\n"
        "- No outlet names. No 'reportedly'.\n"
        "- Max 260 chars."
    ),

    "take": (
        "TASK — POST-MATCH SHARP TAKE\n"
        "Write a reaction post about the FEATURED FIXTURE — that match only.\n\n"
        "⚠ FORMAT — NON-NEGOTIABLE: Every sentence on its own line, separated by a blank line. No prose paragraphs.\n\n"
        "STRUCTURE:\n"
        "  Line 1: Open — calm, knowing. Something that feels like you saw it coming.\n"
        "           Don't recycle 'No shock. No noise.' — be specific to what actually happened.\n"
        "           e.g. 'Messi with the assist. Of course. Game 1 of his last World Cup.'\n"
        "               'Algeria held for 60 minutes. Then the wall came down.'\n"
        "  Line 2–4: Tell the story — 2-3 lines. What happened, what it means, the key moment.\n"
        "  Line 5: Historical parallel — a number, a record, a year that makes this bigger.\n"
        "  Line 6: BetEye organic pivot — NOT a template. Specific to this game.\n"
        "           Show how the data/intelligence angle applies to what just happened.\n"
        "           Examples:\n"
        "             'The xG on Algeria's 63rd minute chance had this written all over it. @BetEye_ 👁'\n"
        "             'Messi's pressing stats in openers. That pattern was always there. @BetEye_ 👁'\n"
        "             'People were shocked. BetEye members weren't watching in surprise — they were watching for confirmation. @BetEye_ 👁'\n"
        "  Line 7: Close — one bold statement or directive. No question mark.\n\n"
        "RULES:\n"
        "- FEATURED FIXTURE only. Real names, real numbers, real moments.\n"
        "- Never name outlets. Never say 'according to'.\n"
        "- At most ONE question mark total.\n"
        "- Max 260 chars.\n\n"
        "EXAMPLE (France vs Senegal, France wins 1-0, Mbappé goal 74'):\n"
        "Mbappé, 74 minutes. Right when Senegal started believing.\n"
        "The opener is always about nerves. France absorbed them until they didn't need to.\n"
        "Mendy made three big stops before that. The wall finally cracked at the wrong time.\n"
        "France have now won 9 of their last 10 WC group stage games.\n"
        "The data had France winning this one. The pattern was clear from the lineup. @BetEye_ 👁\n"
        "Next fixture matters more.\n\n"
        "Max 260 chars."
    ),

    "matchday": (
        "TASK — PRE-MATCH HYPE (ONE GAME ONLY)\n"
        "Write about EXACTLY the fixture in HEADLINE. One match. Nothing else.\n\n"
        "⚠ FORMAT — NON-NEGOTIABLE. Every line on its own, separated by a blank line. No prose paragraphs.\n"
        "Structure (6–7 lines):\n"
        "  Line 1: Match title — HOME VS AWAY in ALL CAPS (e.g. 'JORDAN VS AUSTRIA')\n"
        "  Line 2: Kickoff facts — [TIME] ET · [STADIUM] · [CITY] · Group [X].\n"
        "           If stadium/city are unknown, write ONLY '[TIME] ET · Group [X].'\n"
        "           Never write 'Unrevealed', 'Unknown', or placeholder text.\n"
        "  Line 3: Hook — sharp fact, record, or rivalry specific to THIS match\n"
        "  Line 4: (optional) second hook if it adds weight\n"
        "  Line 5: The duel — one player vs one player, or one stat that defines this game\n"
        "  Line 6: Closing — ONE of: a punchy bold statement, an engagement question, or a BetEye intelligence angle ending with @BetEye_ 👁.\n"
        "           Do NOT default to @BetEye_ every time. Vary it. Only use it when it genuinely adds.\n"
        "           Examples:\n"
        "             'Don't sleep on this one.' (bold)\n"
        "             'Who wins this? Drop your pick 👇' (engagement)\n"
        "             'Whoever wins the midfield battle wins this. @BetEye_ sees exactly where it breaks. 👁' (brand)\n\n"
        "RULES:\n"
        "- ONE match only. Never reference another game.\n"
        "- Real names, real numbers, real history. Nothing invented.\n"
        "- Max ONE question mark total.\n"
        "- Max 260 chars total.\n\n"
        "EXAMPLE OUTPUT:\n"
        "FRANCE VS SENEGAL\n"
        "3PM ET · MetLife Stadium · East Rutherford · Group I.\n"
        "France haven't lost a WC group stage game in 12 years.\n"
        "Senegal ended that streak once. 2002. They remember.\n"
        "Mbappé vs Mendy. Two men who know each other too well.\n"
        "The data knows who carries the weight. @BetEye_ 👁\n"
        "Don't sleep on this one."
    ),

    "news": (
        "TASK — WC 2026 INTELLIGENCE UPDATE\n"
        "Report what happened — sharp, specific, no outlet names.\n\n"
        "⚠ FORMAT — NON-NEGOTIABLE: Every sentence on its own line, separated by a blank line. No prose paragraphs.\n\n"
        "STRUCTURE:\n"
        "  Line 1: The fact. One line. Names, numbers, stakes. Nothing soft.\n"
        "  Line 2-3: Why it changes something — what it means for the tournament.\n"
        "  Line 4 (if applicable): If a related fixture is UPCOMING TODAY and hasn't kicked off yet, reference it by city or time — never repeat a time for a match that already happened.\n"
        "  Line 5: Closing — ONE of: a punchy consequence statement, an engagement hook, or (occasionally) a BetEye angle ending @BetEye_ 👁.\n"
        "           Do NOT add @BetEye_ to every post. Use it at most once every 3-4 posts, when it genuinely fits.\n"
        "           Most of the time, close with a bold statement or engagement line instead.\n\n"
        "RULES:\n"
        "- No outlet names. No 'reportedly' or 'according to'.\n"
        "- Real names, real numbers. Nothing vague.\n"
        "- At most ONE question mark total. Prefer no question marks.\n"
        "- Max 260 chars.\n\n"
        "EXAMPLE OUTPUT:\n"
        "Rodri will miss the rest of the World Cup group stage.\n"
        "Spain's midfield shape just changed completely.\n"
        "7.2 ball recoveries per 90 — no one else in this squad does that.\n"
        "That defensive gap is now a tournament-wide conversation.\n"
        "How far can Spain go without him?\n\n"
        "Max 260 chars."
    ),

    "list": (
        "TASK — ORIGINAL RANKED LIST\n"
        "Source is a ranking/list article. Write your OWN curated version. DO NOT credit the outlet.\n\n"
        "FORMAT:\n"
        "  [HOOK — ALL CAPS, 1 line: 'X TEAMS THAT WILL DEFINE WC 2026:']\n\n"
        "  1. [Name/team] — [specific reason, one line]\n"
        "  2. [Name/team] — [specific reason, one line]\n"
        "  ...\n\n"
        + _CLOSING_LINE_GUIDE +
        "\n\nEXAMPLE OUTPUT:\n"
        "5 PLAYERS WHO WILL DECIDE WC 2026:\n\n"
        "1. Mbappé (France) — 12 World Cup goals at 27. Has never gone beyond the quarters with a trophy.\n"
        "2. Vinicius Jr (Brazil) — 3 UCL finals in 4 years. This is his statement tournament.\n"
        "3. Bellingham (England) — Scored the winner in every knockout game of WC 2022 qualifiers.\n"
        "4. Messi (Argentina) — Defending champion. This is the last one. Every minute counts.\n"
        "5. Lamine Yamal (Spain) — 17 years old. Starting for the tournament favourites. No ceiling.\n\n"
        "RT if your pick isn't on this list.\n\n"
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


def _item_is_fresh(item: dict, cutoff: datetime) -> bool:
    """True if the item was collected after cutoff. Breaking items get no special exemption."""
    try:
        ts = datetime.fromisoformat(item.get("collected_at", "2000-01-01T00:00:00+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts > cutoff
    except Exception:
        return True  # keep items we can't parse rather than silently drop them


def _item_has_live_context(item: dict) -> bool:
    """
    Return True if the queue item is contextually relevant right now.
    Rejects items that only mention teams whose matches finished >90 min ago —
    those produce stale out-of-context posts.
    """
    from wc_fixtures import get_todays_fixtures
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fixtures = get_todays_fixtures()
    if not fixtures:
        return True  # no fixture data — give the item the benefit of the doubt

    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    now  = datetime.now(ZoneInfo("America/New_York"))

    mentioned: list[dict] = [
        fx for fx in fixtures
        if fx.get("home", "").lower() in text or fx.get("away", "").lower() in text
    ]
    if not mentioned:
        return True  # item not about today's teams — let it through

    # If ANY mentioned fixture is still live or upcoming, the item is relevant
    from wc_fixtures import _parse_ko
    for fx in mentioned:
        try:
            ko      = _parse_ko(fx)
            elapsed = (now - ko).total_seconds() / 60
            # upcoming (not started yet) or within 110 min of kickoff (match window)
            if elapsed < 110:
                return True
        except Exception:
            return True

    # All mentioned fixtures ended >90 min ago — stale context
    return False


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


def _breaking_daily_count() -> int:
    """How many breaking posts have fired today."""
    state    = _load_json(STATE_FILE, {})
    fired    = state.get("breaking_fired", {})
    today_ts = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return sum(1 for v in fired.values() if v >= today_ts)


def _mins_since_last_breaking() -> float:
    """Minutes since any breaking post fired (independent of scheduled posts)."""
    state = _load_json(STATE_FILE, {})
    fired = state.get("breaking_fired", {})
    if not fired:
        return float("inf")
    latest = max(fired.values())
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(latest)).total_seconds() / 60
    except Exception:
        return float("inf")


def _breaking_already_fired(slug: str) -> bool:
    """True if we already fired breaking news for this match slug in the last 3 hours."""
    state = _load_json(STATE_FILE, {})
    fired: dict = state.get("breaking_fired", {})
    last = fired.get(slug)
    if not last:
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
        return age < 3.0
    except Exception:
        return False


def _mark_breaking_fired(slug: str) -> None:
    state = _load_json(STATE_FILE, {})
    fired: dict = state.get("breaking_fired", {})
    fired[slug] = datetime.now(timezone.utc).isoformat()
    # Keep only last 24h of entries
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    fired  = {k: v for k, v in fired.items() if v > cutoff}
    state["breaking_fired"] = fired
    _save_json(STATE_FILE, state)


def _breaking_has_enough_context(item: dict) -> bool:
    """
    True if breaking news has real live context:
    - A WC fixture is currently in-play, OR
    - The item was collected in the last 20 minutes (very fresh — genuine scoop)
    Either condition is enough. Prevents stale 'breaking' items from jumping the queue.
    """
    from wc_fixtures import get_todays_fixtures, _parse_ko
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))

    # Check for a currently-live fixture (elapsed < 110min)
    for fx in get_todays_fixtures():
        try:
            ko      = _parse_ko(fx)
            elapsed = (now - ko).total_seconds() / 60
            if 0 <= elapsed < 110:
                return True
        except Exception:
            continue

    # Fall back: item must be very fresh
    try:
        ts = datetime.fromisoformat(item.get("collected_at", "2000-01-01T00:00:00+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_mins = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        return age_mins < 20
    except Exception:
        return False


def _get_daily_count() -> int:
    state = _load_json(STATE_FILE, {})
    today = datetime.now(timezone.utc).date().isoformat()
    return state.get("daily_posts", {}).get(today, 0)


def _increment_daily_count(n: int = 1) -> int:
    state = _load_json(STATE_FILE, {})
    today  = datetime.now(timezone.utc).date().isoformat()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    daily  = {k: v for k, v in state.get("daily_posts", {}).items() if k >= cutoff}
    daily[today] = daily.get(today, 0) + n
    state["daily_posts"] = daily
    _save_json(STATE_FILE, state)
    return daily[today]


def _get_mode_count(mode: str) -> int:
    state     = _load_json(STATE_FILE, {})
    today_str = datetime.now(ET).date().isoformat()
    return state.get("daily_mode_counts", {}).get(today_str, {}).get(mode, 0)


def _increment_mode_count(mode: str) -> None:
    state     = _load_json(STATE_FILE, {})
    today_str = datetime.now(ET).date().isoformat()
    counts    = state.setdefault("daily_mode_counts", {}).setdefault(today_str, {})
    counts[mode] = counts.get(mode, 0) + 1
    _save_json(STATE_FILE, state)


def _get_posted_slots() -> set[str]:
    """Return the set of slot keys already posted (survives restarts)."""
    state = _load_json(STATE_FILE, {})
    return set(state.get("posted_slots", []))


def _mark_slot_posted(slot_key: str) -> None:
    """Persist a slot key so it is skipped on restart. Keys are date-stamped; keep last 200."""
    state = _load_json(STATE_FILE, {})
    slots: list[str] = state.get("posted_slots", [])
    if slot_key not in slots:
        slots.append(slot_key)
    state["posted_slots"] = slots[-200:]
    _save_json(STATE_FILE, state)


def _fixture_to_item(fixture: dict, mode: str) -> dict:
    """Synthesise a queue item from fixture data for scheduled matchday/stat posts."""
    home      = fixture["home"]
    away      = fixture["away"]
    group     = fixture.get("group", "?")
    kickoff   = fixture.get("kickoff_et", "TBD")
    _PLACEHOLDER = {"unrevealed", "unknown", "tbd", "tba", "n/a", ""}
    raw_venue = (fixture.get("venue", "") or "").strip()
    raw_city  = (fixture.get("city",  "") or "").strip()
    venue     = "" if raw_venue.lower() in _PLACEHOLDER else raw_venue
    city      = "" if raw_city.lower()  in _PLACEHOLDER else raw_city
    md        = fixture.get("matchday", 1)
    venue_str = f"{venue}, {city}" if venue and city else city or venue
    location  = f"Venue: {venue_str}. " if venue_str else ""
    return {
        "title":        f"{home} vs {away} — WC 2026 Group {group} MD{md}, {kickoff} ET",
        "summary":      (
            f"Kickoff: {kickoff} ET. {location}"
            f"Group {group}, Matchday {md}. "
            f"Teams: {home} and {away}."
        ),
        "source":       "wc_schedule",
        "score":        8,
        "key":          f"sched_{fixture.get('date', '')}_{home}_{away}_{mode}",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "is_breaking":  False,
        "url":          "",
        # Internal — not sent to API. Used by _generate_post and image_gen to
        # scope content to exactly this match, not all of today's fixtures.
        "_fixture":     fixture,
    }


# ---------------------------------------------------------------------------
# Generation — uses /generate/from-source to ground output in actual news
# ---------------------------------------------------------------------------

def _load_intelligence() -> dict:
    return _load_json(INTEL_FILE, {})


def _select_mode(item: dict, is_breaking: bool, post_index: int) -> str:
    """
    Choose content mode for queue-based posts (breaking news path only).
    matchday and stat are NEVER assigned here — those come exclusively from
    scheduled_post_job() which scopes them to a specific fixture.
    """
    if is_breaking:
        return "news"

    if _LIST_TITLE_RE.search(item.get("title", "")):
        return "list"

    # Queue posts: only news / take / list — never matchday or stat
    _QUEUE_MODES   = ["news", "take", "list"]
    _QUEUE_WEIGHTS = [2,      3,      1]

    intel = _load_intelligence()
    mode_perf: dict = intel.get("mode_performance", {})

    if mode_perf:
        weights = [max(mode_perf.get(m, 1.0), 0.1) for m in _QUEUE_MODES]
        return random.choices(_QUEUE_MODES, weights=weights, k=1)[0]

    return random.choices(_QUEUE_MODES, weights=_QUEUE_WEIGHTS, k=1)[0]


async def _generate_post(item: dict, mode: str = "news") -> str | None:
    today       = datetime.now(timezone.utc).strftime("%B %d, %Y")
    pub_approx  = item.get("collected_at", "")[:10]
    angle       = random.choice(ANGLES)
    instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["news"])
    char_limit  = MODE_CHAR_LIMITS.get(mode, 280)

    # WC fixture context injection.
    # For scheduled single-fixture posts, scope to ONLY that match so the model
    # doesn't write about other games. For everything else, inject today's full slate.
    specific_fx = item.get("_fixture")
    if specific_fx and mode in ("matchday", "stat", "take"):
        from wc_fixtures import format_match_context, fetch_fixture_result
        fixture_ctx = format_match_context([specific_fx], "FEATURED FIXTURE")
        # Inject the verified live/final score so the model never halluccinates the scoreline
        live_result = await fetch_fixture_result(specific_fx.get("fixture_id"))
        if live_result and live_result.get("home_goals") is not None:
            hg     = live_result["home_goals"]
            ag     = live_result["away_goals"]
            status = live_result.get("status", "NS")
            elapsed = live_result.get("elapsed")
            home   = specific_fx.get("home", "")
            away   = specific_fx.get("away", "")
            if status in ("FT", "AET", "PEN"):
                score_line = f"VERIFIED FINAL SCORE: {home} {hg} – {ag} {away} (Full Time)"
            elif status in ("1H", "HT", "2H", "ET", "P") and elapsed:
                score_line = f"VERIFIED LIVE SCORE: {home} {hg} – {ag} {away} ({elapsed}')"
            elif status == "HT":
                score_line = f"VERIFIED HALF-TIME SCORE: {home} {hg} – {ag} {away}"
            else:
                score_line = f"VERIFIED SCORE: {home} {hg} – {ag} {away} (status: {status})"
            fixture_ctx = score_line + "\n" + fixture_ctx
        else:
            live_result = None
    else:
        fixture_ctx  = get_fixture_context_block()
        live_result  = None
    fixture_block = f"\n{fixture_ctx}\n" if fixture_ctx else ""

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
        f"DATE COLLECTED: ~{pub_approx}  |  TODAY: {today}\n"
        f"{fixture_block}\n"
        f"ARTICLE CONTENT:\n{item.get('summary', '(no body — use headline only)')}\n\n"
        f"---\n"
        f"SECONDARY ANGLE: {angle}\n\n"
        f"{instruction}"
        f"{learned_block}\n\n"
        f"HARD RULES:\n"
        f"- Only state facts from ARTICLE CONTENT or TODAY'S WC 2026 FIXTURES. Do NOT invent stats.\n"
        + (
            f"- SCORELINE IS VERIFIED ABOVE. Use ONLY those exact goal numbers. "
            f"NEVER invent or guess any score, goal count, or match result.\n"
            if live_result and live_result.get("home_goals") is not None else ""
        ) +
        f"- NEVER mention any media outlet, website, or publication name.\n"
        f"- Be specific — name a player, country, stadium, number, or fixture. Never be vague.\n"
        f"- If a team in the article has an UPCOMING fixture today (not yet started), you may reference it with 'tonight' or '[city]' — never state a kickoff time for a match that has already been played.\n"
        f"- Do not start with 'I'.\n"
        f"- At most ONE question mark in the entire post. Never more than one.\n"
        f"- STATS AND NUMBERS — CRITICAL: Only use specific numbers (goal counts, minutes, career tallies, percentages, caps) that appear EXPLICITLY in the article content provided. "
        f"If a stat is not in the source text, DO NOT include it — omit the claim entirely rather than guess. "
        f"Never use training knowledge to fill in career stats, goal tallies, or match details not present in the source.\n"
        f"- MATCH FRAMING — never describe a goal as a 'winner', 'late winner', 'equaliser', or 'opener' unless that framing is stated in the source. Use only the scoreline context above.\n"
        f"- BANNED PHRASES — do NOT use ANY of these words or phrases, not even close variants: {BANNED_PHRASES}\n"
        f"- Write like a sharp human analyst, not an AI assistant. No hype language, no vague gestures at significance. Every sentence earns its place."
    )

    form_data: dict = {
        "platform":     "twitter",
        "content_type": "idea",
        "idea_count":   "1",
        "text":         source_text,
    }
    if PERSONA_ID:
        form_data["persona_id"] = str(PERSONA_ID)

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                base_url=VOXLY_API_URL,
                headers={"Authorization": f"Bearer {VOXLY_API_KEY}"},
                timeout=httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0),
            ) as client:
                resp = await client.post("/generate/from-source", data=form_data)
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if not results:
                    return None
                text = results[0]["content"].strip()
                break  # success
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            wait = 10 * (attempt + 1)
            log.warning(f"[generate] Attempt {attempt + 1}/3 timed out — retrying in {wait}s ({exc})")
            await asyncio.sleep(wait)
    else:
        log.error(f"[generate] All 3 attempts failed: {last_exc}")
        return None

    import re

    # Step 1: if the model collapsed everything into one block, restore line breaks
    # at sentence boundaries (capital letter or emoji after ". / ! / ?")
    if "\n" not in text:
        text = re.sub(r'([.!?])\s+(?=[A-Z\U0001F300-\U0001FAFF])', r'\1\n', text)

    # Step 2: normalise to blank-line-separated lines for ALL post types.
    # Collapse any existing blank lines → single blank, then ensure every
    # non-empty line is followed by a blank line.
    lines = [l.rstrip() for l in text.splitlines()]
    merged: list[str] = []
    for line in lines:
        if line:
            merged.append(line)
            merged.append("")           # blank line after every content line
        # skip already-blank lines — we're adding our own

    # Strip leading/trailing blank lines then rejoin
    text = "\n".join(merged).strip()

    # Truncate at sentence boundary — never cut mid-sentence.
    # Applies twice: once for the mode char_limit (style cap) and once for
    # TWITTER_CHAR_LIMIT (hard API cap). Both use the same logic.
    def _truncate_to(t: str, limit: int) -> str:
        if len(t) <= limit:
            return t
        kept: list[str] = []
        for part in t.split("\n"):
            candidate = "\n".join(kept + [part]) if kept else part
            if len(candidate) <= limit:
                kept.append(part)
            else:
                break
        clipped = "\n".join(kept).rstrip()
        content_lines = [l for l in clipped.split("\n") if l.strip()]
        while content_lines and not content_lines[-1].rstrip().endswith((".", "!", "?", "👁", "🔥", "⚡", "👇")):
            content_lines.pop()
        return "\n\n".join(content_lines)

    text = _truncate_to(text, char_limit)
    text = _truncate_to(text, TWITTER_CHAR_LIMIT)  # hard cap — never exceeds what Twitter accepts

    return text


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

    breaking_score = mc.get("breaking_score") or BREAKING_SCORE

    log.info(f"[collect] Fetching — breaking≥{breaking_score} | schedule drives regular posts")

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

        # Drop items about finished fixtures before they enter the queue
        candidate = {
            "title":   item["title"],
            "summary": item.get("summary", ""),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        if not _item_has_live_context(candidate):
            skipped_offtopic += 1
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

    # Purge stale items every cycle — old items produce out-of-context posts
    cutoff = datetime.now(timezone.utc) - timedelta(hours=QUEUE_MAX_AGE_HOURS)
    before_purge = len(queue)
    queue = [item for item in queue if _item_is_fresh(item, cutoff)]
    purged = before_purge - len(queue)
    if purged:
        log.info(f"[collect] Purged {purged} stale items (>{QUEUE_MAX_AGE_HOURS:.0f}h old)")

    queue.sort(key=lambda x: (x.get("is_breaking", False), x.get("score", 0)), reverse=True)
    queue = queue[:200]
    _save_json(QUEUE_FILE, queue)

    log.info(
        f"[collect] +{added} queued | "
        f"skipped: {skipped_offtopic} off-topic, {skipped_hist} historical, {skipped_low} low-score | "
        f"breaking: {has_breaking} | queue: {len(queue)}"
    )

    # --- Startup grace period: crawl and build context, don't post yet ---
    elapsed_mins = (datetime.now(timezone.utc) - _AGENT_START_TIME).total_seconds() / 60
    if elapsed_mins < STARTUP_GRACE_MINS:
        log.info(
            f"[collect] Startup grace ({elapsed_mins:.0f}/{STARTUP_GRACE_MINS:.0f}min) — "
            f"crawling only, first post after {STARTUP_GRACE_MINS - elapsed_mins:.0f}min"
        )
        return

    # Breaking items are flagged in the queue and will be picked up by the
    # scheduled breaking slot that fires 1h after each match ends.
    # There is no real-time bypass — the buffer window is intentional.
    if has_breaking:
        log.info(f"[collect] High-priority items queued — breaking slot will pick them up post-match")
    else:
        log.info(f"[collect] {added} new items queued (next scheduled slot will pick them up)")


# ---------------------------------------------------------------------------
# Job 2 — Poster
# ---------------------------------------------------------------------------

async def post_job() -> None:
    log.info("[poster] Starting post run…")

    daily_count = _get_daily_count()
    if daily_count >= DAILY_POST_MAX:
        log.info(f"[poster] Daily cap reached ({daily_count}/{DAILY_POST_MAX}) — skipping")
        return

    posts_this_run = min(POSTS_PER_RUN, DAILY_POST_MAX - daily_count)

    queue: list[dict] = _load_json(QUEUE_FILE, [])
    seen: list        = _load_json(SEEN_FILE, [])
    seen_set          = set(seen)
    perf: list        = _load_json(PERF_FILE, [])

    if not queue:
        log.info("[poster] Queue empty — skipping")
        return

    log.info(f"[poster] Daily: {daily_count}/{DAILY_POST_MAX} posted today. This run: up to {posts_this_run}.")

    posted    = 0
    used_keys: list[str] = []

    for i, item in enumerate(queue):
        if posted >= posts_this_run:
            break

        # Skip items whose only relevant fixtures already finished — avoids out-of-context posts
        if not _item_has_live_context(item):
            log.info(f"[poster] Skipping stale-context item: {item.get('title', '')[:60]}")
            continue

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

            # Images only for matchday posts — other modes post text-only for now
            image_path = None
            if mode == "matchday":
                try:
                    image_path = await generate_post_image(
                        item=item,
                        mode=mode,
                        post_text=text,
                        today_fixtures=get_todays_fixtures(),
                    )
                except Exception as img_err:
                    log.warning(f"[poster] Image generation failed (posting without): {img_err}")

            media_id: str | None = None
            if image_path and not DRY_RUN:
                media_id = upload_media(str(image_path))

            if DRY_RUN:
                fake_id = f"dry_{int(datetime.now(timezone.utc).timestamp())}"
                log.info(
                    f"[poster] [DRY RUN] [{mode}] ({len(text)} chars)"
                    f"{' +image' if image_path else ''}\n{text}\n{'─'*60}"
                )
                posted_id = fake_id
            else:
                try:
                    posted_id = post_tweet(text, reply_to_id=tweet_id_to_reply, media_id=media_id)
                except tweepy.errors.Forbidden:
                    log.error(
                        "[poster] 403 Forbidden from Twitter — app needs Read+Write permissions. "
                        "Update in Developer Portal then regenerate Access Token + Secret."
                    )
                    if image_path:
                        image_path.unlink(missing_ok=True)
                    break  # auth is broken for this run — stop trying
                log.info(
                    f"[poster] Posted {posted_id} [{mode}] ({len(text)} chars)"
                    f"{' +image' if media_id else ''}\n{text}\n{'─'*60}"
                )

            # Clean up temp image file after upload
            if image_path:
                try:
                    image_path.unlink(missing_ok=True)
                except Exception:
                    pass

            seen_set.add(item["key"])
            used_keys.append(item["key"])
            posted += 1

            # Pace posts — don't blast all N at once; wait between each (skip after last)
            if posted < posts_this_run and POST_INTERVAL_SECS > 0:
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
        new_daily = _increment_daily_count(posted)
        log.info(
            f"[poster] Done — {posted}/{posts_this_run} posted this run | "
            f"daily total: {new_daily}/{DAILY_POST_MAX} | queue remaining: {len(queue)}"
        )


# ---------------------------------------------------------------------------
# Job 3 — Scheduled post (fires at pre-calculated fixture-aware times)
# ---------------------------------------------------------------------------

async def scheduled_post_job(mode: str, fixture: dict | None, label: str, slot_key: str = "") -> None:
    """Execute a single scheduled post slot with full mode + daily cap enforcement."""
    log.info(f"[schedule] Slot fired: {label}")

    # Global minimum gap — prevent spam if a breaking post just fired
    SCHED_MIN_GAP_MINS = 20
    gap = _minutes_since_last_post()
    if gap < SCHED_MIN_GAP_MINS:
        log.info(f"[schedule] Too soon after last post ({gap:.0f}min < {SCHED_MIN_GAP_MINS}min) — skipping [{label}]")
        return

    # Daily total cap
    daily_count = _get_daily_count()
    if daily_count >= DAILY_POST_MAX:
        log.info(f"[schedule] Daily cap ({DAILY_POST_MAX}) reached — skipping [{label}]")
        return

    # Per-mode cap
    mode_count = _get_mode_count(mode)
    mode_cap   = MODE_DAILY_CAPS.get(mode, 1)
    if mode_count >= mode_cap:
        log.info(f"[schedule] Mode cap for '{mode}' ({mode_cap}) reached — skipping [{label}]")
        return

    # Build or pick a queue item
    if fixture and mode in ("matchday", "stat"):
        item = _fixture_to_item(fixture, mode)
    elif fixture and mode == "breaking":
        # For breaking slots, prefer queue items about THIS specific fixture's teams.
        # Fall back to fixture-synthesised item if nothing relevant was collected.
        queue    = _load_json(QUEUE_FILE, [])
        seen_set = set(_load_json(SEEN_FILE, []))
        home_lc  = fixture.get("home", "").lower()
        away_lc  = fixture.get("away", "").lower()
        relevant = [
            q for q in queue
            if q["key"] not in seen_set
            and (
                home_lc in (q.get("title", "") + q.get("summary", "")).lower()
                or away_lc in (q.get("title", "") + q.get("summary", "")).lower()
            )
        ]
        if relevant:
            item = max(relevant, key=lambda x: x.get("score", 0))
            log.info(f"[schedule] Breaking: picked {len(relevant)} relevant queue items for {fixture.get('home')} vs {fixture.get('away')}")
        else:
            log.info(f"[schedule] Breaking: no queue items for {fixture.get('home')} vs {fixture.get('away')} — using fixture context")
            item = _fixture_to_item(fixture, mode)
        # Always attach the fixture so the prompt gets the verified score
        item["_fixture"] = fixture
    else:
        queue: list[dict] = _load_json(QUEUE_FILE, [])
        if not queue:
            log.info(f"[schedule] Queue empty — skipping [{label}]")
            return
        # Pick the highest-scoring item not yet seen
        seen_set = set(_load_json(SEEN_FILE, []))
        candidates = [q for q in queue if q["key"] not in seen_set]
        if not candidates:
            log.info(f"[schedule] No unseen queue items — skipping [{label}]")
            return
        item = max(candidates, key=lambda x: x.get("score", 0))

    text = await _generate_post(item, mode=mode)
    if not text:
        log.warning(f"[schedule] Empty generation — skipping [{label}]")
        return

    # Images only for matchday posts
    image_path = None
    if mode == "matchday":
        try:
            image_path = await generate_post_image(
                item=item, mode=mode, post_text=text, today_fixtures=get_todays_fixtures()
            )
        except Exception as img_err:
            log.warning(f"[schedule] Image gen failed (posting without): {img_err}")

    media_id: str | None = None
    if image_path and not DRY_RUN:
        media_id = upload_media(str(image_path))

    if DRY_RUN:
        posted_id = f"dry_{int(datetime.now(timezone.utc).timestamp())}"
        log.info(
            f"[schedule] [DRY RUN] [{mode}]{' +image' if image_path else ''}\n"
            f"{text}\n{'─'*60}"
        )
    else:
        try:
            posted_id = post_tweet(text, media_id=media_id)
        except tweepy.errors.Forbidden:
            log.error(
                "[schedule] 403 Forbidden from Twitter — app needs Read+Write permissions. "
                "Go to Developer Portal → App → User auth settings → set Permissions to 'Read and Write', "
                "then regenerate Access Token + Secret and update .env."
            )
            if image_path:
                image_path.unlink(missing_ok=True)
            return
        log.info(
            f"[schedule] Posted {posted_id} [{mode}]{' +image' if media_id else ''}\n"
            f"{text}\n{'─'*60}"
        )

    if image_path:
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Update state
    _mark_posted()
    _increment_daily_count(1)
    _increment_mode_count(mode)

    # Mark item as seen (for queue-based modes)
    if mode not in ("matchday", "stat") or not fixture:
        seen: list = _load_json(SEEN_FILE, [])
        seen_set = set(seen)
        seen_set.add(item["key"])
        _save_json(SEEN_FILE, list(seen_set)[-5000:])

    # Mark this slot as done — prevents duplicate on restart
    if slot_key:
        _mark_slot_posted(slot_key)

    # Track for performance review
    perf: list = _load_json(PERF_FILE, [])
    perf.append({
        "tweet_id":    posted_id,
        "mode":        mode,
        "text":        text,
        "is_reply":    False,
        "is_breaking": item.get("is_breaking", False),
        "score":       item.get("score", 0),
        "title":       item["title"][:120],
        "source":      item.get("source", ""),
        "posted_at":   datetime.now(timezone.utc).isoformat(),
        "metrics":     None,
    })
    _save_json(PERF_FILE, perf[-200:])


async def schedule_today() -> None:
    """
    Build today's fixture-aware post schedule and register APScheduler date jobs.
    Already-posted slots are skipped. Safe to call on restart or at midnight.
    """
    # Clear any existing slot jobs from a previous schedule build
    for job in scheduler.get_jobs():
        if job.id.startswith("slot_"):
            job.remove()

    fixtures = get_todays_fixtures()
    if not fixtures:
        log.info("[schedule] No fixtures today — no scheduled slots added")
        return

    posted_slots = _get_posted_slots()
    slots = build_daily_schedule(fixtures)

    skipped = [s for s in slots if s.slot_key in posted_slots]
    pending = [s for s in slots if s.slot_key not in posted_slots]

    if skipped:
        log.info(f"[schedule] Skipping {len(skipped)} already-posted slot(s): {[s.slot_key for s in skipped]}")

    log.info(f"[schedule] Today's pending slots ({len(pending)}):\n{describe_schedule(pending)}")

    for i, slot in enumerate(pending):
        job_id = f"slot_{slot.mode}_{i}"
        scheduler.add_job(
            scheduled_post_job,
            trigger="date",
            run_date=slot.run_at,
            kwargs={
                "mode":     slot.mode,
                "fixture":  slot.fixture,
                "label":    slot.label,
                "slot_key": slot.slot_key,
            },
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )


# ---------------------------------------------------------------------------
# Job 4 — Performance tracker (runs every 6h)
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
        f"breaking_score≥{BREAKING_SCORE} | posts_per_run={POSTS_PER_RUN} | "
        f"daily_cap={DAILY_POST_MAX} | "
        f"replies={'on' if ENABLE_REPLIES else 'off'} | dry_run={DRY_RUN}"
    )
    if not PERSONA_ID:
        log.warning("PERSONA_ID not set — run setup.py first")

    # Validate X (Twitter) credentials before anything else
    validate_credentials()

    # Purge stale queue items on startup so old-match content can't sneak into posts
    _queue: list = _load_json(QUEUE_FILE, [])
    _cutoff = datetime.now(timezone.utc) - timedelta(hours=QUEUE_MAX_AGE_HOURS)
    _before = len(_queue)
    _queue = [i for i in _queue if _item_is_fresh(i, _cutoff)]
    if _before - len(_queue):
        log.info(f"[startup] Purged {_before - len(_queue)} stale queue items")
        _save_json(QUEUE_FILE, _queue)

    # Fetch live WC schedule from API Football (falls back to bundled static file if no key)
    await ensure_schedule_fresh()
    # Fetch today's fixtures with UTC kickoff times — this is the authoritative source for scheduling
    await fetch_todays_fixtures_live()

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Refresh full WC schedule every 12h
    scheduler.add_job(
        ensure_schedule_fresh,
        trigger="interval",
        hours=12,
        id="schedule_refresh",
        max_instances=1,
        coalesce=True,
    )

    # Refresh today's fixtures every 30min — keeps UTC kickoff times accurate
    # and picks up any late kickoff adjustments from API Football
    scheduler.add_job(
        fetch_todays_fixtures_live,
        trigger="interval",
        minutes=30,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=30),
        id="todays_fixtures_refresh",
        max_instances=1,
        coalesce=True,
    )

    # Content collector — runs every N minutes, triggers post_job only on breaking news
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

    # Rebuild schedule at 06:00 ET — this is when the broadcast day rolls over.
    # The broadcast day is 06:00 ET → 05:59 ET the next day, so at 06:00 we pick up
    # the new day's fixtures (Portugal, England, etc.) without interfering with late-night
    # games that cross midnight ET (e.g. 00:00 ET kickoffs from the previous schedule build).
    scheduler.add_job(
        schedule_today,
        trigger=CronTrigger(hour=6, minute=0, timezone=ET),
        id="schedule_rebuild",
        max_instances=1,
        coalesce=True,
    )

    # Performance metrics check — 6h after posts go out
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

    # Build today's schedule AFTER scheduler starts (schedule_today adds jobs to it)
    await schedule_today()

    log.info(
        f"Beteye running | collect={initial_collect_mins}min | "
        f"daily_cap={DAILY_POST_MAX} | schedule built | perf_check in 6h"
    )

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Beteye stopped")


if __name__ == "__main__":
    asyncio.run(main())
