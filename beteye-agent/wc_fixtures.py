"""
WC 2026 fixture data — today's matches and upcoming context for the content engine.

Schedule source priority:
  1. /data/wc_schedule_api.json  — fetched from API Football, refreshed every 12h
  2. wc_schedule.json (bundled)  — static fallback when API is unavailable
"""
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger("beteye.fixtures")

ET = ZoneInfo("America/New_York")

# Bundled static schedule — fallback only
_STATIC_SCHEDULE = Path(__file__).parent / "wc_schedule.json"

# Live cache — written to the data volume so it survives restarts
_CACHE_FILE = Path(os.environ.get("DATA_DIR", "/data")) / "wc_schedule_api.json"
_CACHE_MAX_AGE_HOURS = float(os.environ.get("SCHEDULE_CACHE_HOURS", "12"))

# API Football
_APISPORTS_KEY  = os.environ.get("APISPORTS_KEY", "")
_APISPORTS_URL  = "https://v3.football.api-sports.io"
_WC_LEAGUE_ID   = 1     # FIFA World Cup
_WC_SEASON      = 2026


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_is_fresh() -> bool:
    if not _CACHE_FILE.exists():
        return False
    mtime = datetime.fromtimestamp(_CACHE_FILE.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds() < _CACHE_MAX_AGE_HOURS * 3600


def _load_static() -> list[dict]:
    try:
        return json.loads(_STATIC_SCHEDULE.read_text())
    except Exception as e:
        log.warning(f"Could not load static WC schedule: {e}")
        return []


def _load_cache() -> list[dict]:
    try:
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        return []


def _save_cache(fixtures: list[dict]) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2))
        log.info(f"[fixtures] Schedule cache updated — {len(fixtures)} fixtures saved")
    except Exception as e:
        log.warning(f"[fixtures] Could not write schedule cache: {e}")


def _parse_matchday(round_str: str) -> int:
    """Extract matchday number from 'Group Stage - 1' / 'Group Stage - 2' etc."""
    import re
    m = re.search(r'(\d+)\s*$', round_str.strip())
    return int(m.group(1)) if m else 0


async def _fetch_group_map(client: httpx.AsyncClient) -> dict[str, str]:
    """
    Fetch standings and return {team_name: group_letter} map.
    e.g. {'Mexico': 'A', 'South Africa': 'A', 'France': 'I', ...}
    """
    try:
        resp = await client.get(
            f"{_APISPORTS_URL}/standings",
            params={"league": _WC_LEAGUE_ID, "season": _WC_SEASON},
            headers={"x-apisports-key": _APISPORTS_KEY},
        )
        resp.raise_for_status()
        data  = resp.json()
        group_map: dict[str, str] = {}
        for league_entry in data.get("response", []):
            for group in league_entry.get("league", {}).get("standings", []):
                for entry in group:
                    raw_group = entry.get("group", "")        # e.g. "Group A"
                    team_name = entry.get("team", {}).get("name", "")
                    import re
                    m = re.search(r'Group\s+([A-L])\b', raw_group, re.IGNORECASE)
                    if m and team_name:
                        group_map[team_name] = m.group(1).upper()
        log.info(f"[fixtures] Group map built: {len(group_map)} teams")
        return group_map
    except Exception as e:
        log.warning(f"[fixtures] Could not fetch group map: {e}")
        return {}


def _api_fixture_to_local(f: dict, group_map: dict[str, str]) -> dict | None:
    """Convert one API Football fixture dict to our schema."""
    try:
        fixture   = f["fixture"]
        league    = f["league"]
        teams     = f["teams"]
        round_str = league.get("round", "")

        # Only include group stage matches
        if "Group Stage" not in round_str:
            return None

        raw_date = fixture.get("date", "")
        if not raw_date:
            return None
        try:
            utc_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            et_dt  = utc_dt.astimezone(ET)
        except Exception:
            return None

        home_name = teams["home"]["name"]
        away_name = teams["away"]["name"]
        group     = group_map.get(home_name) or group_map.get(away_name) or "?"

        return {
            "date":       et_dt.date().isoformat(),
            "home":       home_name,
            "away":       away_name,
            "group":      group,
            "matchday":   _parse_matchday(round_str),
            "kickoff_et": et_dt.strftime("%H:%M"),
            "venue":      fixture.get("venue", {}).get("name", "") or "",
            "city":       fixture.get("venue", {}).get("city", "") or "",
            "fixture_id": fixture.get("id"),
            "status":     fixture.get("status", {}).get("short", "NS"),
            "home_logo":  teams["home"].get("logo", "") or "",
            "away_logo":  teams["away"].get("logo", "") or "",
            "confirmed":  True,
        }
    except Exception as e:
        log.debug(f"[fixtures] Could not parse fixture: {e}")
        return None


async def fetch_and_cache_schedule() -> bool:
    """
    Fetch the full WC 2026 schedule from API Football and write to cache.
    Returns True on success. No-ops and returns False if no API key configured.
    """
    if not _APISPORTS_KEY:
        log.debug("[fixtures] APISPORTS_KEY not set — skipping live schedule fetch")
        return False

    log.info("[fixtures] Fetching WC 2026 schedule from API Football…")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            group_map = await _fetch_group_map(client)

            resp = await client.get(
                f"{_APISPORTS_URL}/fixtures",
                params={"league": _WC_LEAGUE_ID, "season": _WC_SEASON},
                headers={"x-apisports-key": _APISPORTS_KEY},
            )
            resp.raise_for_status()
            data = resp.json()

        raw = data.get("response", [])
        if not raw:
            log.warning(f"[fixtures] API returned 0 fixtures (errors: {data.get('errors')})")
            return False

        fixtures = [r for f in raw if (r := _api_fixture_to_local(f, group_map)) is not None]
        fixtures.sort(key=lambda m: (m.get("date", ""), m.get("kickoff_et", "")))

        known = sum(1 for f in fixtures if f["group"] != "?")
        log.info(
            f"[fixtures] {len(raw)} total → {len(fixtures)} group stage "
            f"({known} with group letter, {len(fixtures) - known} unknown)"
        )
        _save_cache(fixtures)
        return True

    except Exception as e:
        log.warning(f"[fixtures] API Football fetch failed: {e}")
        return False


async def ensure_schedule_fresh() -> None:
    """Call at agent startup and once daily to keep the cache current."""
    if _cache_is_fresh():
        log.debug("[fixtures] Schedule cache is fresh — skipping fetch")
        return
    ok = await fetch_and_cache_schedule()
    if not ok and not _CACHE_FILE.exists():
        log.info("[fixtures] Using bundled static schedule as fallback")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_schedule() -> list[dict]:
    """Load live cache if fresh, else bundled static file."""
    if _CACHE_FILE.exists():
        return _load_cache()
    return _load_static()


def get_todays_fixtures() -> list[dict]:
    """Return matches kicking off today (ET), sorted by kickoff."""
    today_str = datetime.now(ET).date().isoformat()
    matches = [m for m in _load_schedule() if m.get("date") == today_str]
    return sorted(matches, key=lambda m: m.get("kickoff_et", "00:00"))


def get_upcoming_fixtures(days: int = 2) -> list[dict]:
    """Return matches over the next N days (ET), not including today."""
    today = datetime.now(ET).date()
    end   = today + timedelta(days=days)
    matches = [
        m for m in _load_schedule()
        if today < date.fromisoformat(m.get("date", "2000-01-01")) <= end
    ]
    return sorted(matches, key=lambda m: (m.get("date", ""), m.get("kickoff_et", "")))


def format_match_context(fixtures: list[dict], label: str) -> str:
    """Format a fixture list as a compact block for prompt injection."""
    if not fixtures:
        return ""
    lines = [f"{label}:"]
    for m in fixtures:
        kickoff   = m.get("kickoff_et", "TBD")
        venue_str = f", {m['venue']}" if m.get("venue") else ""
        city_str  = f" ({m['city']})"  if m.get("city")  else ""
        group     = m.get("group", "?")
        md        = m.get("matchday", "?")
        lines.append(
            f"  {m['home']} vs {m['away']} — "
            f"Group {group}, MD{md}, {kickoff} ET{venue_str}{city_str}"
        )
    return "\n".join(lines)


def get_fixture_context_block() -> str:
    """
    Best available fixture context string to inject into generation prompts.
    Prefers today; falls back to next 2 days.
    """
    today = get_todays_fixtures()
    if today:
        return format_match_context(today, "TODAY'S WC 2026 FIXTURES")

    upcoming = get_upcoming_fixtures(days=2)
    if upcoming:
        next_date = upcoming[0].get("date", "")
        label = f"NEXT WC 2026 FIXTURES ({next_date})" if next_date else "UPCOMING WC 2026 FIXTURES"
        return format_match_context(upcoming[:6], label)

    return ""


def has_fixtures_today() -> bool:
    return len(get_todays_fixtures()) > 0


def fixture_count_today() -> int:
    return len(get_todays_fixtures())
