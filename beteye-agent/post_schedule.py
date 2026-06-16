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


def _kickoff_et(fixture: dict) -> datetime:
    """Parse kickoff as ET-aware datetime."""
    date_str = fixture["date"]
    time_str = fixture.get("kickoff_et", "12:00")
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=ET)


def is_marquee(fixture: dict) -> bool:
    return bool(
        MARQUEE_TEAMS & {fixture.get("home", ""), fixture.get("away", "")}
    )


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

    slots: list[PostSlot] = []
    stat_count = 0

    by_kickoff = sorted(fixtures, key=lambda f: f.get("kickoff_et", "00:00"))

    # ── 1. Matchday posts — 5h before each kickoff ─────────────────────────
    for fx in by_kickoff:
        kickoff = _kickoff_et(fx)
        run_at  = kickoff - timedelta(hours=5)
        label   = f"matchday: {fx['home']} vs {fx['away']}"

        if run_at < now:
            if now < kickoff:
                # Missed window but game hasn't kicked off — post ASAP
                run_at = now + timedelta(minutes=5)
            else:
                continue  # game already started/ended — skip

        slots.append(PostSlot(run_at=run_at, mode="matchday", fixture=fx, label=label))

    # ── 2. Stat posts — 90min before kickoff, marquee only, max 1/day ──────
    for fx in by_kickoff:
        if not is_marquee(fx):
            continue
        kickoff = _kickoff_et(fx)
        run_at  = kickoff - timedelta(minutes=90)
        label   = f"stat: {fx['home']} vs {fx['away']}"

        if run_at < now:
            continue  # missed — no ASAP for stat (loses context)

        slots.append(PostSlot(run_at=run_at, mode="stat", fixture=fx, label=label))
        stat_count += 1
        if stat_count >= MODE_DAILY_CAPS["stat"]:
            break

    # ── 3. Take posts — post-match buzz windows, max 2/day ─────────────────
    # One take after the first match finishes, one after the last.
    # Single-fixture day: halftime (KO+60) + full-time (KO+110).
    take_times: list[tuple[datetime, dict | None]] = []

    if len(by_kickoff) == 1:
        ko = _kickoff_et(by_kickoff[0])
        take_times = [(ko + timedelta(minutes=60), None), (ko + timedelta(minutes=110), None)]
    elif len(by_kickoff) >= 2:
        first_ko = _kickoff_et(by_kickoff[0])
        last_ko  = _kickoff_et(by_kickoff[-1])
        take_times = [
            (first_ko + timedelta(minutes=110), None),
            (last_ko  + timedelta(minutes=110), None),
        ]

    for take_at, fx in take_times:
        if take_at <= now:
            continue
        slots.append(PostSlot(
            run_at=take_at,
            mode="take",
            fixture=fx,
            label="take: post-match reaction",
        ))

    # ── 4. News post — 09:30 ET fixed slot ─────────────────────────────────
    news_at = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if news_at <= now:
        news_at = now + timedelta(minutes=10)  # ASAP if we're past 09:30

    slots.append(PostSlot(run_at=news_at, mode="news", fixture=None, label="news: morning briefing"))

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
