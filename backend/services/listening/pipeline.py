"""The listening pipeline: X search -> filters -> AI check -> profile check -> draft.

Every stage can drop a post with a reason; nothing is ever posted from here. A person
reviews each draft in the queue and sends it from X's own reply box.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.listening import (
    DoNotContact, ListeningCampaign, ListeningCandidate, ListeningState,
    OutreachDraft, OutreachEvent, OutreachTemplate,
)
from services.listening.classifier import classify_post
from services.listening.drafter import build_link, check_draft, new_code, pick_template, render
from services.listening.filters import age_signals, harm_signals, is_opt_out, matched_query_terms
from services.listening.receipts import find_proof
from services.x_api import XApiError, XClient

logger = logging.getLogger(__name__)

ONE_TOUCH_DAYS = 90
UNREVIEWED_RETENTION_DAYS = 14
RETENTION_DAYS = 90

# Profile locations that point to a market, for the allowed-markets check.
_MARKET_HINTS = {
    "NG": ["nigeria", "naija", "lagos", "abuja", "port harcourt", "ibadan", "kano", "enugu", "benin city"],
    "GH": ["ghana", "accra", "kumasi"],
    "KE": ["kenya", "nairobi", "mombasa"],
    "ZA": ["south africa", "johannesburg", "cape town", "durban"],
    "GB": ["united kingdom", "england", "london", "manchester", "liverpool", "scotland", "wales"],
    "US": ["united states", "usa", "new york", "california", "texas", "florida"],
}


def _location_market(location: str | None) -> str | None:
    loc = (location or "").lower()
    for market, hints in _MARKET_HINTS.items():
        if any(h in loc for h in hints):
            return market
    return None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _blocked_authors(db: AsyncSession, author_ids: set[str]) -> dict[str, str]:
    """Authors who must not be contacted: do-not-contact, contacted recently, or already queued."""
    if not author_ids:
        return {}
    blocked: dict[str, str] = {}
    dnc = await db.execute(select(DoNotContact.x_author_id).where(DoNotContact.x_author_id.in_(author_ids)))
    for (author,) in dnc:
        blocked[author] = "do_not_contact"
    since = datetime.now(timezone.utc) - timedelta(days=ONE_TOUCH_DAYS)
    recent = await db.execute(
        select(ListeningCandidate.x_author_id, OutreachDraft.status)
        .join(OutreachDraft, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(
            ListeningCandidate.x_author_id.in_(author_ids),
            ((OutreachDraft.status == "sent") & (OutreachDraft.sent_at >= since)) | (OutreachDraft.status == "queued"),
        )
    )
    for author, status in recent:
        blocked.setdefault(author, "contacted_recently" if status == "sent" else "already_queued")
    return blocked


def _drop(candidate: ListeningCandidate, reason: str) -> None:
    candidate.stage = "dropped"
    candidate.drop_reason = reason


async def poll_campaign(db: AsyncSession, campaign: ListeningCampaign, x_client: XClient | None = None) -> dict:
    """One search round for a campaign. Returns stage counts for logging and the dashboard."""
    stats = {"read": 0, "dropped": 0, "drafted": 0}
    if campaign.status != "active":
        return stats

    client = x_client or XClient(db, campaign)
    # An attempt counts toward the search interval even if the budget pace holds it back.
    campaign.last_polled_at = datetime.now(timezone.utc)
    await db.commit()
    posts, newest_id = await client.search_recent(campaign.x_query, campaign.since_id, campaign.max_results_per_poll)
    if newest_id:
        campaign.since_id = newest_id
    stats["read"] = len(posts)

    existing = set((await db.execute(
        select(ListeningCandidate.x_post_id).where(
            ListeningCandidate.campaign_id == campaign.id,
            ListeningCandidate.x_post_id.in_([p["id"] for p in posts] or [""]),
        )
    )).scalars())

    candidates: list[ListeningCandidate] = []
    for post in posts:
        if post["id"] in existing or post.get("author_id") == settings.X_ACCOUNT_USER_ID:
            continue
        candidate = ListeningCandidate(
            campaign_id=campaign.id,
            x_post_id=post["id"],
            x_author_id=post.get("author_id"),
            text=post.get("text", ""),
            lang=post.get("lang"),
            posted_at=_parse_time(post.get("created_at")),
            matched_terms=matched_query_terms(post.get("text", ""), campaign.x_query),
        )
        db.add(candidate)
        candidates.append(candidate)
    # These reads are already paid for: save the cursor and the posts now, so a failure
    # in a later step can't make the next round read (and pay for) them again.
    await db.commit()

    # Word lists and contact history first: free, and they never send a post to the AI.
    blocked = await _blocked_authors(db, {c.x_author_id for c in candidates if c.x_author_id})
    survivors = []
    for c in candidates:
        if harm_signals(c.text, campaign.harm_terms):
            _drop(c, "harm_words")
        elif age_signals(c.text):
            _drop(c, "age_words")
        elif c.x_author_id in blocked:
            _drop(c, blocked[c.x_author_id])
        else:
            survivors.append(c)

    # AI check, one post at a time; fails closed.
    classified = []
    for c in survivors:
        verdict = await classify_post(c.text)
        c.verdict = verdict
        if not verdict["eligible"]:
            _drop(c, verdict["reason"])
            continue
        market = verdict.get("market", "UNKNOWN")
        if campaign.allowed_markets and market not in ("UNKNOWN", *campaign.allowed_markets):
            _drop(c, "market")
            continue
        c.stage = "classified"
        classified.append(c)

    # Profiles only for posts that passed, so user reads stay rare.
    try:
        profiles = await client.users_by_ids(list({c.x_author_id for c in classified if c.x_author_id}))
    except XApiError as exc:
        logger.warning("Listening campaign %s: profile lookup unavailable (%s); dropping this round's matches", campaign.id, exc)
        for c in classified:
            _drop(c, "x_unavailable")
        classified, profiles = [], {}
    templates = list((await db.execute(
        select(OutreachTemplate).where(OutreachTemplate.campaign_id == campaign.id)
    )).scalars())
    queued_authors: set[str] = set()
    for c in classified:
        profile = profiles.get(c.x_author_id or "", {})
        bio = f"{profile.get('description', '')} {profile.get('location', '')}"
        location_market = _location_market(profile.get("location"))
        if not profile or profile.get("protected"):
            _drop(c, "profile_unavailable")
        elif harm_signals(bio, campaign.harm_terms) or age_signals(bio):
            _drop(c, "profile_signal")
        elif campaign.allowed_markets and location_market and location_market not in campaign.allowed_markets:
            _drop(c, "market")
        elif c.x_author_id in queued_authors:
            _drop(c, "already_queued")
        else:
            c.x_author_handle = profile.get("username")
            proof = await find_proof(c.verdict.get("teams", []))
            template = pick_template(templates, c.verdict["intent"], have_proof=proof is not None)
            if template is None:
                _drop(c, "no_approved_template")
                continue
            code = new_code()
            text = render(template.body, proof, build_link(campaign.link_base, code))
            if check_draft(text):
                _drop(c, "draft_check_failed")
                continue
            await db.flush()  # candidate id for the draft
            db.add(OutreachDraft(candidate_id=c.id, template_id=template.id, text=text, proof=proof, code=code))
            c.stage = "drafted"
            queued_authors.add(c.x_author_id or "")
            stats["drafted"] += 1

    stats["dropped"] = sum(1 for c in candidates if c.stage == "dropped")
    await db.commit()
    return stats


async def _get_state(db: AsyncSession, key: str) -> str | None:
    row = await db.get(ListeningState, key)
    return row.value if row else None


async def _set_state(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(ListeningState, key)
    if row:
        row.value = value
    else:
        db.add(ListeningState(key=key, value=value))


async def record_event(db: AsyncSession, code: str, event_type: str, source: str, occurred_at: datetime) -> bool:
    """Insert once per (code, type); returns False for a repeat."""
    exists = await db.execute(select(OutreachEvent.id).where(OutreachEvent.code == code, OutreachEvent.type == event_type))
    if exists.first():
        return False
    db.add(OutreachEvent(code=code, type=event_type, source=source, occurred_at=occurred_at))
    return True


async def add_do_not_contact(db: AsyncSession, author_id: str, reason: str) -> None:
    if not await db.get(DoNotContact, author_id):
        db.add(DoNotContact(x_author_id=author_id, reason=reason))


async def poll_mentions(db: AsyncSession, x_client: XClient | None = None) -> dict:
    """Replies to sent outreach become 'replied' events; any stop request ends contact for good."""
    stats = {"read": 0, "replies": 0, "opt_outs": 0}
    if not settings.X_ACCOUNT_USER_ID:
        return stats
    client = x_client or XClient(db)
    posts, newest_id = await client.mentions(settings.X_ACCOUNT_USER_ID, await _get_state(db, "mentions_since_id"))
    stats["read"] = len(posts)
    for post in posts:
        replied_to = [r["id"] for r in post.get("referenced_tweets") or [] if r.get("type") == "replied_to"]
        draft = None
        if replied_to:
            draft = (await db.execute(
                select(OutreachDraft).where(OutreachDraft.reply_post_id.in_(replied_to))
            )).scalars().first()
        when = _parse_time(post.get("created_at")) or datetime.now(timezone.utc)
        if draft and await record_event(db, draft.code, "replied", "x", when):
            stats["replies"] += 1
        if is_opt_out(post.get("text", "")) and post.get("author_id"):
            await add_do_not_contact(db, post["author_id"], "asked_to_stop")
            if draft:
                await record_event(db, draft.code, "opt_out", "x", when)
            stats["opt_outs"] += 1
    if newest_id:
        await _set_state(db, "mentions_since_id", newest_id)
    await db.commit()
    return stats


async def purge_listening_data(db: AsyncSession) -> dict:
    """Unreviewed candidates go after 14 days; everything except attribution after 90."""
    now = datetime.now(timezone.utc)
    unreviewed = await db.execute(
        delete(ListeningCandidate).where(
            ListeningCandidate.created_at < now - timedelta(days=UNREVIEWED_RETENTION_DAYS),
            ListeningCandidate.stage.in_(["new", "classified", "dropped", "drafted"]),
        )
    )
    # Sent outreach keeps its code (events and stats hang on it) but loses the personal data.
    old = now - timedelta(days=RETENTION_DAYS)
    scrubbed = await db.execute(
        update(ListeningCandidate)
        .where(ListeningCandidate.created_at < old, ListeningCandidate.text.is_not(None))
        .values(text=None, x_author_handle=None, x_author_id=None, verdict=None)
    )
    await db.execute(
        update(OutreachDraft)
        .where(OutreachDraft.created_at < old, OutreachDraft.text.is_not(None))
        .values(text=None, reply_url=None)
    )
    await db.commit()
    return {"deleted": unreviewed.rowcount or 0, "scrubbed": scrubbed.rowcount or 0}
