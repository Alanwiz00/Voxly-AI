"""
One-shot setup of BetEye's starter listening campaigns, built from the team's curated phrase list.

The $12/month plan: two campaigns get the budget ($6 each, 10 posts per search, every
30 minutes, paced evenly through the month); the other three are seeded with a $0 budget
so they can't spend until someone gives them one on the Listening page.

Everything is created paused, and every template is created unapproved: replies only draft
once a template has an ARCON certificate number (Listening page -> Templates). Safe to re-run:
campaigns and templates that already exist (by name) are left untouched.

Usage (inside the backend container, after the owner has signed in once):
    python seed_beteye_listening.py --owner you@example.com
    python seed_beteye_listening.py --dry-run          # print the queries, touch nothing
"""
import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.engine import make_url

from core.config import settings
from main import _migrate_db
from db.models.listening import ListeningCampaign, OutreachTemplate
from db.models.user import User
from db.postgres import AsyncSessionLocal, init_db
from services.listening.drafter import validate_template

SIGNUP_LINK = "https://t.me/Beteyebot/BETEYE"
# Dropped at X, so they're never billed; the full harm and age checks still run on everything else.
# Tipster adverts and bet-slip screenshots almost always carry a link or an image.
EXCLUDE = ' -is:retweet -has:links -has:media -addicted -"lost everything"'
FOOTER = "\n\n18+ · Play responsibly"

PROOF_TEMPLATE = {
    "name": "Live proof",
    "intent": "seeking_live_alerts",
    "body": "BetEye flagged a {alert_type} at {minute}' in {match}, and it {outcome}.\n\nFree live alerts on Telegram: {link}" + FOOTER,
}

# The two funded campaigns' daily caps add up to 30 (the spec's 30 per X account per day).
CAMPAIGNS = [
    {
        "name": "Live: in-play tips & alerts",
        "daily_cap": 15,
        "monthly_budget_usd": 6,
        "poll_every_minutes": 30,
        # Dropped for cost: "live betting", "live odds", "match momentum", "live football stats" (high volume, low intent)
        "phrases": [
            "in-play betting", "live football tips", "live match predictions", "in-play predictions",
            "live betting alerts", "real-time football alerts", "in-play opportunities", "any live match tips",
            "live match analysis",
        ],
        "templates": [
            PROOF_TEMPLATE,
            {"name": "Live, no proof", "intent": "any",
             "body": "BetEye sends live match alerts on Telegram when a game shifts: goals, cards, corners. Every result is published, misses included.\n\nTry it free: {link}" + FOOTER},
        ],
    },
    {
        "name": "Live: goals, overs & corners",
        "daily_cap": 6,
        "monthly_budget_usd": 0,
        "poll_every_minutes": 60,
        "phrases": [
            "goal alerts", "next goal prediction", "late goal prediction", "second half goals",
            "over 0.5 live", "over 1.5 live", "corners prediction", "goalkeeper saves betting",
        ],
        "templates": [
            PROOF_TEMPLATE,
            {"name": "Goals, no proof", "intent": "any",
             "body": "BetEye watches live games for goal and corner pressure and sends an alert on Telegram when it builds. Every result is published, misses included.\n\nFree: {link}" + FOOTER},
        ],
    },
    {
        "name": "Looking for an app or channel",
        "daily_cap": 8,
        "monthly_budget_usd": 0,
        "poll_every_minutes": 60,
        "phrases": [
            "betting app recommendations", "football prediction app", "best prediction app",
            "AI football predictions", "AI betting tools", "betting analytics", "football analytics app",
            "betting signals", "football signals", "betting alert bot", "Telegram betting bot",
            "football tips Telegram", "prediction channel", "football stats tool", "match analysis tool",
        ],
        "templates": [
            {"name": "App pitch", "intent": "any",
             "body": "BetEye is a free Telegram app that sends live football alerts from match data, and every alert's result is published, misses included.\n\nHave a look: {link}" + FOOTER},
        ],
    },
    {
        "name": "Nigeria: Pidgin & bookmakers",
        "daily_cap": 15,
        "monthly_budget_usd": 6,
        "poll_every_minutes": 30,
        # "SportyBet booking code" -> "who get booking code": tipsters post codes as plain text nonstop;
        # this keeps the people asking for one. "SportyBet odds" dropped for volume.
        "phrases": [
            "who get prediction", "drop your predictions", "wetin una dey predict", "which match go win",
            "which game dey today", "who go score today", "which team go score", "today game prediction",
            "who get booking code", "SportyBet predictions", "Bet9ja predictions", "1xBet predictions",
            "BetKing predictions", "Betway predictions", "Melbet predictions", "Parimatch predictions",
        ],
        "templates": [
            PROOF_TEMPLATE,
            {"name": "Nigeria, no proof", "intent": "any",
             "body": "BetEye sends free live alerts on Telegram when a match turns: goals, cards, corners. Every result is published, wins and misses.\n\n{link}" + FOOTER},
        ],
    },
    {
        # Seeded for later: tipster accounts post these phrases nonstop, so check volume first.
        "name": "Pre-match predictions (later)",
        "daily_cap": 5,
        "monthly_budget_usd": 0,
        "poll_every_minutes": 60,
        "phrases": [
            "football predictions", "football prediction today", "today's predictions", "match predictions",
            "soccer predictions", "betting tips", "best football tips", "any predictions", "match winner prediction",
            "over 1.5 prediction", "over 2.5 prediction", "BTTS prediction", "both teams to score",
            "weekend predictions", "EPL predictions", "Champions League predictions", "weekend football tips",
            "football accumulator",
        ],
        "templates": [
            {"name": "Live, not pre-match", "intent": "any",
             "body": "BetEye's alerts are live, not pre-match picks: it flags when a game shifts, and every result is published, misses included.\n\nFree on Telegram: {link}" + FOOTER},
        ],
    },
]


def build_query(phrases: list[str]) -> str:
    return "(" + " OR ".join(f'"{p}"' for p in phrases) + ")" + EXCLUDE


def check_presets() -> list[str]:
    problems = []
    for c in CAMPAIGNS:
        query = build_query(c["phrases"])
        if len(query) > settings.X_QUERY_MAX_CHARS:
            problems.append(f'{c["name"]}: query is {len(query)} characters (limit {settings.X_QUERY_MAX_CHARS})')
        for t in c["templates"]:
            for error in validate_template(t["body"], t["intent"]):
                problems.append(f'{c["name"]} / {t["name"]}: {error}')
    return problems


async def seed(owner_email: str) -> None:
    # Say where this is writing: the Listening page only shows campaigns from the
    # database the deployed backend uses.
    url = make_url(settings.DATABASE_URL)
    print(f"Seeding database {url.database} on {url.host}:{url.port or 5432}\n")
    await init_db()
    await _migrate_db()  # same column updates the backend applies on startup
    async with AsyncSessionLocal() as db:
        owner = (await db.execute(select(User).where(User.email == owner_email))).scalar_one_or_none()
        if not owner or not owner.is_admin:
            sys.exit(f"{owner_email} must be an admin who has signed in to Voxly at least once.")

        for c in CAMPAIGNS:
            campaign = (await db.execute(
                select(ListeningCampaign).where(ListeningCampaign.name == c["name"])
            )).scalar_one_or_none()
            created = campaign is None
            if created:
                campaign = ListeningCampaign(
                    owner_id=owner.id, name=c["name"], x_query=build_query(c["phrases"]),
                    harm_terms=[], allowed_markets=["NG"], link_base=SIGNUP_LINK,
                    daily_cap=c["daily_cap"], monthly_budget_usd=c["monthly_budget_usd"],
                    max_results_per_poll=10, poll_every_minutes=c["poll_every_minutes"], status="paused",
                )
                db.add(campaign)
                await db.flush()
            existing = set((await db.execute(
                select(OutreachTemplate.name).where(OutreachTemplate.campaign_id == campaign.id)
            )).scalars())
            new_templates = [t for t in c["templates"] if t["name"] not in existing]
            for t in new_templates:
                db.add(OutreachTemplate(campaign_id=campaign.id, name=t["name"], intent=t["intent"], body=t["body"]))
            print(f'{"created" if created else "exists "}  {c["name"]:<32} {len(c["phrases"]):>2} phrases  '
                  f'{len(campaign.x_query):>3} chars  +{len(new_templates)} templates')
        await db.commit()
    print("\nAll campaigns are paused and all templates unapproved. Two have a $6 budget; the rest $0."
          "\nNext: Listening page -> Check volume, add each template's ARCON certificate number, then activate.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--owner", default=(settings.ADMIN_EMAILS.split(",")[0].strip() or None),
                        help="admin email that owns the campaigns (default: first of ADMIN_EMAILS)")
    parser.add_argument("--dry-run", action="store_true", help="print the queries and stop")
    args = parser.parse_args()

    problems = check_presets()
    if problems:
        sys.exit("Fix these before seeding:\n  " + "\n  ".join(problems))
    if args.dry_run:
        for c in CAMPAIGNS:
            query = build_query(c["phrases"])
            print(f'{c["name"]} ({len(query)} chars, cap {c["daily_cap"]}/day, ${c["monthly_budget_usd"]}/month, every {c["poll_every_minutes"]} min)\n  {query}\n')
        return
    if not args.owner:
        sys.exit("Pass --owner you@example.com (or set ADMIN_EMAILS).")
    asyncio.run(seed(args.owner))


if __name__ == "__main__":
    main()
