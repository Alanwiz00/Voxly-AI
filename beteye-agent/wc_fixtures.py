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

# Short-lived today cache — refreshed every 30min so kickoff times stay accurate
_TODAY_CACHE_FILE     = Path(os.environ.get("DATA_DIR", "/data")) / "todays_fixtures.json"
_TODAY_CACHE_MAX_MINS = 30

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

        _PLACEHOLDER = {"unrevealed", "unknown", "tbd", "tba", "n/a", ""}
        raw_venue = (fixture.get("venue", {}).get("name", "") or "").strip()
        raw_city  = (fixture.get("venue", {}).get("city", "") or "").strip()
        venue = "" if raw_venue.lower() in _PLACEHOLDER else raw_venue
        city  = "" if raw_city.lower()  in _PLACEHOLDER else raw_city

        return {
            "date":        et_dt.date().isoformat(),
            "home":        home_name,
            "away":        away_name,
            "group":       group,
            "matchday":    _parse_matchday(round_str),
            "kickoff_utc": utc_dt.isoformat(),          # authoritative — used for all scheduling math
            "kickoff_et":  et_dt.strftime("%H:%M"),     # display only
            "venue":       venue,
            "city":        city,
            "fixture_id":  fixture.get("id"),
            "status":      fixture.get("status", {}).get("short", "NS"),
            "home_logo":   teams["home"].get("logo", "") or "",
            "away_logo":   teams["away"].get("logo", "") or "",
            "confirmed":   True,
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


def _today_cache_is_fresh() -> bool:
    if not _TODAY_CACHE_FILE.exists():
        return False
    age_mins = (datetime.now() - datetime.fromtimestamp(_TODAY_CACHE_FILE.stat().st_mtime)).total_seconds() / 60
    return age_mins < _TODAY_CACHE_MAX_MINS


async def fetch_todays_fixtures_live() -> list[dict]:
    """
    Fetch only today's WC 2026 fixtures from API Football (by date).
    Stores result in the short-lived today cache. Returns empty list if no key or fetch fails.
    This is called at startup and every 30min during the day so kickoff times are always accurate.
    """
    if not _APISPORTS_KEY:
        log.debug("[fixtures] APISPORTS_KEY not set — skipping today's live fetch")
        return []

    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
    now_et   = datetime.now(_ET)
    today_et = now_et.date()

    # Always fetch today AND tomorrow in UTC terms.
    # Late-evening ET games (e.g. 21:00 ET = 01:00 UTC next day) live on tomorrow's API date.
    # The broadcast-day filter in get_todays_fixtures() decides what's actually "today".
    fetch_dates = [
        today_et.isoformat(),
        (today_et + timedelta(days=1)).isoformat(),
    ]

    log.info(f"[fixtures] Fetching today's live fixtures for {fetch_dates} …")
    raw_all: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for d in fetch_dates:
                resp = await client.get(
                    f"{_APISPORTS_URL}/fixtures",
                    params={"league": _WC_LEAGUE_ID, "season": _WC_SEASON, "date": d},
                    headers={"x-apisports-key": _APISPORTS_KEY},
                )
                resp.raise_for_status()
                raw_all.extend(resp.json().get("response", []))
    except Exception as e:
        log.warning(f"[fixtures] Today's live fetch failed: {e}")
        return []

    # Build group map from full cache so we can annotate group letters
    group_map: dict[str, str] = {}
    for m in _load_schedule():
        if m.get("group", "?") != "?":
            group_map[m["home"]] = m["group"]
            group_map[m["away"]] = m["group"]

    fixtures = [r for f in raw_all if (r := _api_fixture_to_local(f, group_map)) is not None]
    fixtures.sort(key=lambda m: m.get("kickoff_utc", m.get("kickoff_et", "")))

    if fixtures:
        try:
            _TODAY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _TODAY_CACHE_FILE.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2))
            log.info(f"[fixtures] Today cache updated — {len(fixtures)} fixtures (UTC times from API)")
        except Exception as e:
            log.warning(f"[fixtures] Could not write today cache: {e}")
    else:
        log.warning("[fixtures] API returned 0 fixtures for today")

    return fixtures


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
    """Load live cache if available, else bundled static file."""
    if _CACHE_FILE.exists():
        return _load_cache()
    log.warning("[fixtures] API cache missing — using static fallback (kickoff times may be approximate)")
    return _load_static()


def _load_today_cache() -> list[dict]:
    try:
        return json.loads(_TODAY_CACHE_FILE.read_text())
    except Exception:
        return []


def _broadcast_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """
    Return (start, end) of the current 'broadcast day'.
    A broadcast day runs 06:00 ET → 05:59 ET the following day, so that
    games kicking off after midnight ET (e.g. 01:00 ET) belong to the
    previous evening's schedule.
    """
    day_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < day_start:
        day_start -= timedelta(days=1)
    day_end = day_start + timedelta(hours=24)
    return day_start, day_end


def _parse_ko(m: dict) -> datetime:
    """Return timezone-aware kickoff datetime. Prefers kickoff_utc, falls back to kickoff_et."""
    utc_str = m.get("kickoff_utc", "")
    if utc_str:
        try:
            return datetime.fromisoformat(utc_str).astimezone(ET)
        except ValueError:
            pass
    date_str = m.get("date", "")
    time_str = m.get("kickoff_et", "00:00")
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=ET)


def get_todays_fixtures() -> list[dict]:
    """
    Return matches in the current broadcast day (06:00 ET → 05:59 ET next day),
    sorted by actual kickoff time.

    Source priority:
      1. /data/todays_fixtures.json  — live from API Football, refreshed every 30min
      2. /data/wc_schedule_api.json  — full season cache (12h TTL)
      3. wc_schedule.json (bundled)  — static fallback
    """
    now = datetime.now(ET)
    day_start, day_end = _broadcast_day_bounds(now)

    # Prefer short-lived today cache (has accurate UTC kickoff times)
    source = _load_today_cache() if _TODAY_CACHE_FILE.exists() else _load_schedule()

    result = []
    for m in source:
        try:
            ko = _parse_ko(m)
        except (ValueError, KeyError):
            continue
        if day_start <= ko < day_end:
            result.append(m)

    return sorted(result, key=_parse_ko)


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


async def fetch_fixture_result(fixture_id: int | None) -> dict | None:
    """
    Fetch current score and status for a fixture by API Football ID.
    Returns dict with home_goals, away_goals, status, elapsed — or None on failure.
    """
    if not _APISPORTS_KEY or not fixture_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_APISPORTS_URL}/fixtures",
                params={"id": fixture_id},
                headers={"x-apisports-key": _APISPORTS_KEY},
            )
            resp.raise_for_status()
            data = resp.json().get("response", [])
            if not data:
                return None
            f = data[0]
            return {
                "home_goals": f["goals"].get("home"),
                "away_goals": f["goals"].get("away"),
                "status":     f["fixture"]["status"].get("short", "NS"),
                "elapsed":    f["fixture"]["status"].get("elapsed"),
            }
    except Exception as e:
        log.warning(f"[fixtures] fetch_fixture_result({fixture_id}) failed: {e}")
        return None
