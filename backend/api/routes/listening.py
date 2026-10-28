"""Listening & outreach: campaigns, approved templates, the review queue, and results.

Admin-only, except POST /listening/events, which BetEye calls with an HMAC signature.
Nothing here posts to X: the reviewer sends each reply from X's own reply box.
"""
import hashlib
import hmac
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from api.deps import AdminUser, DB
from core.config import settings
from db.models.listening import (
    DoNotContact, ListeningCampaign, ListeningCandidate, OutreachDraft, OutreachEvent, OutreachTemplate,
)
from services.listening.drafter import check_draft, validate_template
from services.listening.pipeline import ONE_TOUCH_DAYS, add_do_not_contact, poll_campaign, record_event
from services.x_api import XApiError, XClient, XPaceLimit, month_spend, pace_allowance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/listening", tags=["listening"])

_CODE_RE = re.compile(r"^vx_[A-Za-z0-9]{6,32}$")
_STATUS_ID_RE = re.compile(r"/status(?:es)?/(\d+)")
_MARKET_RE = re.compile(r"^[A-Z]{2}$")


def _today_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


async def _get_campaign(db, campaign_id: int) -> ListeningCampaign:
    campaign = await db.get(ListeningCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


async def _sent_today(db, campaign_id: int) -> int:
    return (await db.execute(
        select(func.count(OutreachDraft.id))
        .join(ListeningCandidate, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(ListeningCandidate.campaign_id == campaign_id, OutreachDraft.status == "sent",
               OutreachDraft.sent_at >= _today_start())
    )).scalar() or 0


async def _serialize_campaign(db, c: ListeningCampaign) -> dict:
    queued = (await db.execute(
        select(func.count(OutreachDraft.id))
        .join(ListeningCandidate, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(ListeningCandidate.campaign_id == c.id, OutreachDraft.status == "queued")
    )).scalar() or 0
    return {
        "id": c.id,
        "name": c.name,
        "x_query": c.x_query,
        "harm_terms": c.harm_terms or [],
        "allowed_markets": c.allowed_markets or [],
        "link_base": c.link_base,
        "daily_cap": c.daily_cap,
        "monthly_budget_usd": c.monthly_budget_usd,
        "max_results_per_poll": c.max_results_per_poll,
        "poll_every_minutes": c.poll_every_minutes,
        "last_polled_at": c.last_polled_at.isoformat() if c.last_polled_at else None,
        "status": c.status,
        "spend_this_month_usd": round(await month_spend(db, c.id), 4),
        "pace_allowance_usd": round(pace_allowance(c.monthly_budget_usd), 4),
        "queued": queued,
        "sent_today": await _sent_today(db, c.id),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Campaigns ─────────────────────────────────────────────────────────────────

class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    x_query: str = Field(min_length=1, max_length=1024)
    harm_terms: list[str] = []
    allowed_markets: list[str] = []
    link_base: str = Field(default="", max_length=512)
    daily_cap: int = Field(default=15, ge=1, le=500)
    monthly_budget_usd: float = Field(default=6.0, ge=0)  # the $12/month plan funds two campaigns at $6
    max_results_per_poll: int = Field(default=10, ge=10, le=100)
    poll_every_minutes: int = Field(default=30, ge=10, le=1440)


class CampaignPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    x_query: str | None = Field(default=None, min_length=1, max_length=1024)
    harm_terms: list[str] | None = None
    allowed_markets: list[str] | None = None
    link_base: str | None = Field(default=None, max_length=512)
    daily_cap: int | None = Field(default=None, ge=1, le=500)
    monthly_budget_usd: float | None = Field(default=None, ge=0)
    max_results_per_poll: int | None = Field(default=None, ge=10, le=100)
    poll_every_minutes: int | None = Field(default=None, ge=10, le=1440)
    status: str | None = None


def _clean_campaign_fields(data: dict) -> dict:
    query = data.get("x_query")
    if query is not None and len(query) > settings.X_QUERY_MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"X allows {settings.X_QUERY_MAX_CHARS} characters per search; this one is {len(query)}. Split it into two campaigns.",
        )
    if "allowed_markets" in data and data["allowed_markets"] is not None:
        markets = [m.strip().upper() for m in data["allowed_markets"] if m.strip()]
        bad = [m for m in markets if not _MARKET_RE.match(m)]
        if bad:
            raise HTTPException(status_code=400, detail=f"Markets must be 2-letter country codes: {', '.join(bad)}")
        data["allowed_markets"] = markets
    if "harm_terms" in data and data["harm_terms"] is not None:
        data["harm_terms"] = [t.strip() for t in data["harm_terms"] if t.strip()]
    if data.get("status") is not None and data["status"] not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="status must be active or paused")
    return data


@router.get("/campaigns")
async def list_campaigns(admin: AdminUser, db: DB):
    campaigns = (await db.execute(select(ListeningCampaign).order_by(ListeningCampaign.id))).scalars()
    return {
        "campaigns": [await _serialize_campaign(db, c) for c in campaigns],
        "spend_this_month_usd": round(await month_spend(db), 4),
        "monthly_budget_usd": settings.LISTENING_MONTHLY_BUDGET_USD,
        "x_configured": bool(settings.X_BEARER_TOKEN),
    }


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignIn, admin: AdminUser, db: DB):
    data = _clean_campaign_fields(body.model_dump())
    campaign = ListeningCampaign(owner_id=admin.id, status="paused", **data)  # new campaigns start paused
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return await _serialize_campaign(db, campaign)


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, body: CampaignPatch, admin: AdminUser, db: DB):
    campaign = await _get_campaign(db, campaign_id)
    data = _clean_campaign_fields(body.model_dump(exclude_unset=True))
    if data.get("status") == "active" and not campaign.link_base and not data.get("link_base"):
        raise HTTPException(status_code=400, detail="Set the signup link before activating the campaign")
    if "x_query" in data and data["x_query"] != campaign.x_query:
        campaign.since_id = None  # a new query starts its own cursor
    for key, value in data.items():
        setattr(campaign, key, value)
    await db.commit()
    await db.refresh(campaign)
    return await _serialize_campaign(db, campaign)


@router.post("/pause-all")
async def pause_all(admin: AdminUser, db: DB):
    """Kill switch: stop every campaign."""
    result = await db.execute(
        update(ListeningCampaign).where(ListeningCampaign.status == "active").values(status="paused")
    )
    await db.commit()
    return {"paused": result.rowcount or 0}


@router.post("/campaigns/{campaign_id}/size")
async def size_campaign(campaign_id: int, admin: AdminUser, db: DB):
    """Count last week's matching posts ($0.005) and estimate the monthly read cost."""
    campaign = await _get_campaign(db, campaign_id)
    try:
        weekly = await XClient(db, campaign).count_recent(campaign.x_query)
    except XApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    await db.commit()
    monthly = round(weekly * 30 / 7)
    return {
        "posts_last_7_days": weekly,
        "est_posts_per_month": monthly,
        "est_read_cost_per_month_usd": round(monthly * settings.X_PRICE_POST_READ, 2),
    }


@router.post("/campaigns/{campaign_id}/poll")
async def poll_now(campaign_id: int, admin: AdminUser, db: DB):
    """Run one search round now instead of waiting for the 10-minute schedule."""
    campaign = await _get_campaign(db, campaign_id)
    if campaign.status != "active":
        raise HTTPException(status_code=400, detail="Activate the campaign first")
    try:
        return await poll_campaign(db, campaign)
    except XPaceLimit as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except XApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    intent: str = "any"
    body: str = Field(min_length=1, max_length=1000)
    arcon_cert_no: str | None = Field(default=None, max_length=64)
    active: bool = True


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    intent: str | None = None
    body: str | None = Field(default=None, min_length=1, max_length=1000)
    arcon_cert_no: str | None = Field(default=None, max_length=64)
    active: bool | None = None


def _serialize_template(t: OutreachTemplate) -> dict:
    return {
        "id": t.id, "campaign_id": t.campaign_id, "name": t.name, "intent": t.intent, "body": t.body,
        "arcon_cert_no": t.arcon_cert_no, "approved": bool(t.approved_at and t.arcon_cert_no),
        "approved_at": t.approved_at.isoformat() if t.approved_at else None, "active": t.active,
    }


@router.get("/campaigns/{campaign_id}/templates")
async def list_templates(campaign_id: int, admin: AdminUser, db: DB):
    await _get_campaign(db, campaign_id)
    rows = (await db.execute(
        select(OutreachTemplate).where(OutreachTemplate.campaign_id == campaign_id).order_by(OutreachTemplate.id)
    )).scalars()
    return [_serialize_template(t) for t in rows]


@router.post("/campaigns/{campaign_id}/templates", status_code=201)
async def create_template(campaign_id: int, body: TemplateIn, admin: AdminUser, db: DB):
    await _get_campaign(db, campaign_id)
    errors = validate_template(body.body, body.intent)
    if errors:
        raise HTTPException(status_code=400, detail=" · ".join(errors))
    cert = (body.arcon_cert_no or "").strip() or None
    template = OutreachTemplate(
        campaign_id=campaign_id, name=body.name, intent=body.intent, body=body.body, active=body.active,
        arcon_cert_no=cert, approved_at=datetime.now(timezone.utc) if cert else None,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _serialize_template(template)


@router.patch("/templates/{template_id}")
async def update_template(template_id: int, body: TemplatePatch, admin: AdminUser, db: DB):
    template = await db.get(OutreachTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    data = body.model_dump(exclude_unset=True)
    new_body = data.get("body", template.body)
    errors = validate_template(new_body, data.get("intent", template.intent))
    if errors:
        raise HTTPException(status_code=400, detail=" · ".join(errors))
    if new_body != template.body and "arcon_cert_no" not in data:
        # Approval covers the exact wording: new copy needs a new certificate.
        template.arcon_cert_no, template.approved_at = None, None
    if "arcon_cert_no" in data:
        cert = (data.pop("arcon_cert_no") or "").strip() or None
        template.arcon_cert_no = cert
        template.approved_at = datetime.now(timezone.utc) if cert else None
    for key, value in data.items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return _serialize_template(template)


# ── Review queue ──────────────────────────────────────────────────────────────

def _serialize_draft(d: OutreachDraft, c: ListeningCandidate) -> dict:
    return {
        "id": d.id, "code": d.code, "text": d.text, "proof": d.proof, "status": d.status, "edited": d.edited,
        "template_id": d.template_id, "sent_at": d.sent_at.isoformat() if d.sent_at else None,
        "reply_url": d.reply_url, "created_at": d.created_at.isoformat() if d.created_at else None,
        "post": {
            "id": c.x_post_id, "author_id": c.x_author_id, "author_handle": c.x_author_handle,
            "text": c.text, "lang": c.lang, "posted_at": c.posted_at.isoformat() if c.posted_at else None,
            "matched_terms": c.matched_terms or [], "verdict": c.verdict,
        },
    }


async def _get_draft(db, draft_id: int) -> tuple[OutreachDraft, ListeningCandidate]:
    draft = await db.get(OutreachDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft, await db.get(ListeningCandidate, draft.candidate_id)


@router.get("/campaigns/{campaign_id}/queue")
async def get_queue(campaign_id: int, admin: AdminUser, db: DB):
    campaign = await _get_campaign(db, campaign_id)
    rows = await db.execute(
        select(OutreachDraft, ListeningCandidate)
        .join(ListeningCandidate, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(ListeningCandidate.campaign_id == campaign_id, OutreachDraft.status == "queued")
        .order_by(OutreachDraft.created_at)
    )
    return {
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status},
        "daily_cap": campaign.daily_cap,
        "sent_today": await _sent_today(db, campaign_id),
        "drafts": [_serialize_draft(d, c) for d, c in rows],
    }


class DraftEdit(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.patch("/drafts/{draft_id}")
async def edit_draft(draft_id: int, body: DraftEdit, admin: AdminUser, db: DB):
    draft, candidate = await _get_draft(db, draft_id)
    if draft.status != "queued":
        raise HTTPException(status_code=400, detail="Only queued drafts can be edited")
    errors = check_draft(body.text)
    if errors:
        raise HTTPException(status_code=400, detail=" · ".join(errors))
    if draft.code not in body.text:
        raise HTTPException(status_code=400, detail="Keep the signup link: it carries this draft's tracking code")
    draft.text, draft.edited = body.text.strip(), True
    await db.commit()
    return _serialize_draft(draft, candidate)


class SentIn(BaseModel):
    reply_url: str | None = Field(default=None, max_length=512)


@router.post("/drafts/{draft_id}/sent")
async def mark_sent(draft_id: int, body: SentIn, admin: AdminUser, db: DB):
    draft, candidate = await _get_draft(db, draft_id)
    if draft.status != "queued":
        raise HTTPException(status_code=400, detail="Draft is not in the queue")
    campaign = await _get_campaign(db, candidate.campaign_id)
    if await _sent_today(db, campaign.id) >= campaign.daily_cap:
        raise HTTPException(status_code=429, detail=f"Daily cap of {campaign.daily_cap} reached for this campaign")
    if candidate.x_author_id and await db.get(DoNotContact, candidate.x_author_id):
        raise HTTPException(status_code=409, detail="This person is on the do-not-contact list")
    recent = (await db.execute(
        select(func.count(OutreachDraft.id))
        .join(ListeningCandidate, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(ListeningCandidate.x_author_id == candidate.x_author_id, OutreachDraft.status == "sent",
               OutreachDraft.sent_at >= datetime.now(timezone.utc) - timedelta(days=ONE_TOUCH_DAYS))
    )).scalar() or 0
    if candidate.x_author_id and recent:
        raise HTTPException(status_code=409, detail=f"Already contacted in the last {ONE_TOUCH_DAYS} days")

    reply_post_id = None
    if body.reply_url:
        match = _STATUS_ID_RE.search(body.reply_url)
        if not match:
            raise HTTPException(status_code=400, detail="Reply URL should look like https://x.com/<you>/status/<id>")
        reply_post_id = match.group(1)
    draft.status, draft.sent_at, draft.sent_by = "sent", datetime.now(timezone.utc), admin.id
    draft.reply_url, draft.reply_post_id = body.reply_url, reply_post_id
    candidate.stage = "sent"
    await db.commit()
    return _serialize_draft(draft, candidate)


class SkipIn(BaseModel):
    do_not_contact: bool = False


@router.post("/drafts/{draft_id}/skip")
async def skip_draft(draft_id: int, body: SkipIn, admin: AdminUser, db: DB):
    draft, candidate = await _get_draft(db, draft_id)
    if draft.status != "queued":
        raise HTTPException(status_code=400, detail="Draft is not in the queue")
    draft.status = "skipped"
    candidate.stage, candidate.drop_reason = "dropped", "skipped_by_reviewer"
    if body.do_not_contact and candidate.x_author_id:
        await add_do_not_contact(db, candidate.x_author_id, "reviewer")
    await db.commit()
    return _serialize_draft(draft, candidate)


# ── Do-not-contact ────────────────────────────────────────────────────────────

class DncIn(BaseModel):
    x_author_id: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="manual", max_length=64)


@router.get("/do-not-contact")
async def list_dnc(admin: AdminUser, db: DB):
    rows = (await db.execute(select(DoNotContact).order_by(DoNotContact.added_at.desc()))).scalars()
    return [{"x_author_id": r.x_author_id, "reason": r.reason, "added_at": r.added_at.isoformat()} for r in rows]


@router.post("/do-not-contact", status_code=201)
async def add_dnc(body: DncIn, admin: AdminUser, db: DB):
    await add_do_not_contact(db, body.x_author_id, body.reason)
    await db.commit()
    return {"x_author_id": body.x_author_id}


@router.delete("/do-not-contact/{author_id}", status_code=204)
async def remove_dnc(author_id: str, admin: AdminUser, db: DB):
    row = await db.get(DoNotContact, author_id)
    if row:
        await db.delete(row)
        await db.commit()


# ── Results ───────────────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/stats")
async def campaign_stats(campaign_id: int, admin: AdminUser, db: DB):
    campaign = await _get_campaign(db, campaign_id)
    stages = dict((await db.execute(
        select(ListeningCandidate.stage, func.count()).where(ListeningCandidate.campaign_id == campaign_id)
        .group_by(ListeningCandidate.stage)
    )).all())
    drops = dict((await db.execute(
        select(ListeningCandidate.drop_reason, func.count())
        .where(ListeningCandidate.campaign_id == campaign_id, ListeningCandidate.stage == "dropped")
        .group_by(ListeningCandidate.drop_reason)
    )).all())
    events = dict((await db.execute(
        select(OutreachEvent.type, func.count())
        .join(OutreachDraft, OutreachDraft.code == OutreachEvent.code)
        .join(ListeningCandidate, OutreachDraft.candidate_id == ListeningCandidate.id)
        .where(ListeningCandidate.campaign_id == campaign_id)
        .group_by(OutreachEvent.type)
    )).all())
    spend = await month_spend(db, campaign_id)
    replies = events.get("replied", 0)
    return {
        "campaign_id": campaign.id,
        "posts_found": sum(stages.values()),
        "stages": stages,
        "drop_reasons": drops,
        "sent": stages.get("sent", 0),
        "events": events,
        "spend_this_month_usd": round(spend, 4),
        "cost_per_reply_usd": round(spend / replies, 2) if replies else None,
    }


# ── BetEye events (HMAC, no user auth) ────────────────────────────────────────

@router.post("/events", status_code=204)
async def receive_event(request: Request, db: DB):
    """Signup and payment events from BetEye, signed with LISTENING_WEBHOOK_SECRET.

    Signature = hex HMAC-SHA256 of "<X-Voxly-Timestamp>.<raw body>"; rejected after 5 minutes.
    """
    secret = settings.LISTENING_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=503, detail="Events are not configured")
    raw = await request.body()
    timestamp = request.headers.get("x-voxly-timestamp", "")
    signature = request.headers.get("x-voxly-signature", "")
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Stale or missing timestamp")
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Bad signature")

    try:
        payload = json.loads(raw)
        code, event_type = str(payload["code"]), str(payload["event"])
        occurred_at = datetime.fromisoformat(str(payload["at"]).replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Expected {code, event, at}")
    if not _CODE_RE.match(code) or event_type not in ("bot_start", "paid"):
        raise HTTPException(status_code=400, detail="Unknown code format or event type")

    known = (await db.execute(select(OutreachDraft.id).where(OutreachDraft.code == code))).first()
    if not known:
        # Acknowledged so BetEye stops retrying, but nothing to attribute it to.
        logger.warning("Outreach event for unknown code %s ignored", code)
        return Response(status_code=204)
    await record_event(db, code, event_type, "beteye", occurred_at)
    await db.commit()
    return Response(status_code=204)
