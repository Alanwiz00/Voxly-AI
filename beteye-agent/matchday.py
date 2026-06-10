"""
WC 2026 match-day detection.

2026 World Cup: June 11 – July 19, 2026
Format: 48 teams, 16 groups of 3 → Round of 32 → R16 → QF → SF → Final
80 total matches. Most days in the window have at least 2 matches.
"""
import os
from datetime import date, datetime, timezone

WC_START = date(2026, 6, 11)
WC_END   = date(2026, 7, 19)  # Final day

# Days with no matches — between semifinals and 3rd-place / final.
# Add more if needed; override completely via REST_DAYS env var (comma-separated YYYY-MM-DD).
_DEFAULT_REST_DAYS: set[date] = {
    date(2026, 7, 12),  # rest between SF and 3rd-place
    date(2026, 7, 13),
    date(2026, 7, 16),  # rest between 3rd-place and Final
    date(2026, 7, 17),
    date(2026, 7, 18),
}

_env_rest = os.environ.get("WC_REST_DAYS", "")
REST_DAYS: set[date] = (
    {date.fromisoformat(d.strip()) for d in _env_rest.split(",") if d.strip()}
    if _env_rest.strip()
    else _DEFAULT_REST_DAYS
)

# Kick-off window in UTC — most WC matches fall 13:00-23:00 UTC
LIVE_START_HOUR = int(os.environ.get("LIVE_START_HOUR", "12"))
LIVE_END_HOUR   = int(os.environ.get("LIVE_END_HOUR", "23"))


def is_wc_period() -> bool:
    return WC_START <= datetime.now(timezone.utc).date() <= WC_END


def is_match_day() -> bool:
    today = datetime.now(timezone.utc).date()
    return WC_START <= today <= WC_END and today not in REST_DAYS


def is_live_window() -> bool:
    """True during the hours when WC matches are actually being played."""
    now = datetime.now(timezone.utc)
    return is_match_day() and LIVE_START_HOUR <= now.hour <= LIVE_END_HOUR


def get_match_config() -> dict:
    """
    Returns interval/threshold overrides for the current moment.
    Collect interval is in minutes; None means use the default from env.
    """
    if is_live_window():
        # Matches in progress — maximum aggression
        return {
            "collect_interval_mins": float(os.environ.get("MATCHDAY_COLLECT_MINS", "10")),
            "min_threshold":         1,    # post after just 1 new item
            "min_gap_mins":          15,   # post every 15 min during live matches
            "breaking_score":        3,    # almost everything qualifies as breaking
        }
    elif is_match_day():
        # Match day but outside live hours — pre/post-match analysis window
        return {
            "collect_interval_mins": float(os.environ.get("MATCHDAY_COLLECT_MINS", "10")),
            "min_threshold":         2,
            "min_gap_mins":          40,
            "breaking_score":        5,
        }
    else:
        # Normal / off-day
        return {
            "collect_interval_mins": None,
            "min_threshold":         None,
            "min_gap_mins":          None,
            "breaking_score":        int(os.environ.get("BREAKING_SCORE_THRESHOLD", "6")),
        }
