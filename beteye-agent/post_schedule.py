"""
Beteye post schedule builder — WC 2026 fixture-aware daily cadence.

Slot logic:
  matchday  — 5h before each fixture's kickoff (one per match)
  stat      — 90min before kickoff, marquee fixtures only, max 1/day
  take      — post-match window; max 2/day
  news      — 09:30 ET daily slot, falls back to ASAP if missed
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Teams that reliably generate the most pre-match content and engagement
MARQUEE_TEAMS: frozenset[str] = frozenset({
    "Brazil", "France", "Argentina", "England", "Spain",
    "Germany", "Portugal", "Netherlands", "Belgium",
    "Italy", "Croatia", "Mexico", "USA", "Colombia",
    "Senegal", "Japan", "South Korea", "Uruguay",
})

# Hard daily caps per mode
MODE_DAILY_CAPS: dict[str, int] = {
    "matchday": 99,  # one per fixture, uncapped
    "stat":      1,
    "take":      2,
    "news":      1,
    "list":      1,
}

DAILY_POST_MAX = 15  # ceiling on any single day


@dataclass
class PostSlot:
    run_at: datetime         # timezone-aware, in ET
    mode: str
    fixture: dict | None     # specific fixture (None for take/news)
    label: str
    slot_key: str = ""       # stable dedup key — survives restarts


def _kickoff_et(fixture: dict) -> datetime:
    """
    Return timezone-aware kickoff datetime in ET.
    Prefers kickoff_utc (from API Football) for accuracy; falls back to kickoff_et string.
    """
    utc_str = fixture.get("kickoff_utc", "")
    if utc_str:
        try:
            return datetime.fromisoformat(utc_str).astimezone(ET)
        except (ValueError, TypeError):
            pass
    date_str = fixture["date"]
    time_str = fixture.get("kickoff_et", "12:00")
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=ET)


def is_marquee(fixture: dict) -> bool:
    return bool(MARQUEE_TEAMS & {fixture.get("home", ""), fixture.get("away", "")})


def _hype_score(fixture: dict) -> int:
    """Count of marquee teams in a fixture — used to pick the best stat slot."""
    return sum(1 for t in (fixture.get("home", ""), fixture.get("away", "")) if t in MARQUEE_TEAMS)


def build_daily_schedule(
    fixtures: list[dict],
    now: datetime | None = None,
) -> list[PostSlot]:
    """
    Build today's post slots from a list of today's fixtures.
    Slots already past by more than 30min are dropped entirely.
    Slots missed by ≤30min are rescheduled for now+5min (ASAP).
    """
    if now is None:
        now = datetime.now(ET)

    today_str = now.date().isoformat()
    slots: list[PostSlot] = []
    stat_count = 0

    # Sort by actual ET datetime, not time string ("00:00" < "15:00" alphabetically but
    # a midnight game on June 17 kicks off AFTER a 21:00 game on June 16).
    by_kickoff = sorted(fixtures, key=_kickoff_et)

    # ── 1. Matchday posts — 5h before each kickoff ─────────────────────────
    for fx in by_kickoff:
        kickoff  = _kickoff_et(fx)
        run_at   = kickoff - timedelta(hours=5)
        label    = f"matchday: {fx['home']} vs {fx['away']}"
        slot_key = f"matchday_{fx.get('date', today_str)}_{fx['home']}_{fx['away']}"

        if run_at < now:
            if now < kickoff:
                # Missed window but game hasn't kicked off — post ASAP
                run_at = now + timedelta(minutes=5)
            else:
                continue  # game already started/ended — skip entirely

        slots.append(PostSlot(run_at=run_at, mode="matchday", fixture=fx, label=label, slot_key=slot_key))

    # ── 2. Stat post — 90min before kickoff, single most-hyped marquee game ─
    # Sort marquee fixtures by hype (both teams marquee > one team) then by kickoff.
    marquee_by_hype = sorted(
        [fx for fx in by_kickoff if is_marquee(fx)],
        key=lambda f: (-_hype_score(f), _kickoff_et(f)),
    )
    for fx in marquee_by_hype:
        kickoff  = _kickoff_et(fx)
        run_at   = kickoff - timedelta(minutes=90)
        label    = f"stat: {fx['home']} vs {fx['away']}"
        slot_key = f"stat_{fx.get('date', today_str)}_{fx['home']}_{fx['away']}"

        if run_at < now:
            continue  # missed — no ASAP; stat loses context after kickoff

        slots.append(PostSlot(run_at=run_at, mode="stat", fixture=fx, label=label, slot_key=slot_key))
        stat_count += 1
        if stat_count >= MODE_DAILY_CAPS["stat"]:
            break

    # ── 3. Take posts — post-match reaction for the most hyped fixtures ─────
    # Pick top-2 by hype score (both-marquee > one-marquee > none).
    # Tiebreak: prefer LATER kickoffs — bigger games tend to kick off later and draw more post-match buzz.
    # Each take fires 110min after that fixture's kickoff (~full time + stoppage).
    by_hype = sorted(by_kickoff, key=lambda f: (-_hype_score(f), -_kickoff_et(f).timestamp()))
    take_fixtures = by_hype[: MODE_DAILY_CAPS["take"]]

    for fx in take_fixtures:
        ko      = _kickoff_et(fx)
        take_at = ko + timedelta(minutes=110)
        if take_at <= now:
            continue
        slug     = f"{fx['home']}_{fx['away']}"
        slot_key = f"take_{fx.get('date', today_str)}_{slug}"
        slots.append(PostSlot(
            run_at=take_at,
            mode="take",
            fixture=fx,
            label=f"take: {fx['home']} vs {fx['away']} reaction",
            slot_key=slot_key,
        ))

    # ── 4. News post — 09:30 ET fixed slot ─────────────────────────────────
    news_at = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if news_at <= now:
        news_at = now + timedelta(minutes=10)  # ASAP if we're past 09:30

    slots.append(PostSlot(
        run_at=news_at,
        mode="news",
        fixture=None,
        label="news: morning briefing",
        slot_key=f"news_{today_str}",
    ))

    slots.sort(key=lambda s: s.run_at)
    return slots


def describe_schedule(slots: list[PostSlot]) -> str:
    """Human-readable schedule summary for logs."""
    if not slots:
        return "  (no slots)"
    lines = []
    for s in slots:
        lines.append(f"  {s.run_at.strftime('%H:%M ET')} → [{s.mode.upper()}] {s.label}")
    return "\n".join(lines)
