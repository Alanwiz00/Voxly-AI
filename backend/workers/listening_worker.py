"""Celery tasks for X listening. Registered on the crawl worker's app (see crawl_worker.py)."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db.models.listening import ListeningCampaign
from services.listening.pipeline import poll_campaign, poll_mentions, purge_listening_data
from services.x_api import XApiError, XBudgetExceeded, XPaceLimit
from workers.crawl_worker import AsyncSessionLocal, _run, celery_app

logger = logging.getLogger(__name__)


def is_due(last_polled_at: datetime | None, every_minutes: int, now: datetime) -> bool:
    # A minute of slack, so a beat tick landing a few seconds early doesn't push a
    # 30-minute campaign to 40.
    return last_polled_at is None or now - last_polled_at >= timedelta(minutes=every_minutes - 1)


async def _poll_all_campaigns() -> dict:
    results = {}
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ListeningCampaign.id, ListeningCampaign.last_polled_at, ListeningCampaign.poll_every_minutes)
            .where(ListeningCampaign.status == "active")
        )).all()
    campaign_ids = [cid for cid, last, every in rows if is_due(last, every or 10, now)]
    for campaign_id in campaign_ids:
        # A fresh session per campaign, so one campaign's failure can't roll back another's work
        async with AsyncSessionLocal() as db:
            campaign = await db.get(ListeningCampaign, campaign_id)
            try:
                results[campaign_id] = await poll_campaign(db, campaign)
            except XPaceLimit as exc:
                logger.info("Listening campaign %s waiting for its budget pace: %s", campaign_id, exc)
                results[campaign_id] = {"skipped": "pace"}
            except XBudgetExceeded as exc:
                logger.warning("Listening campaign %s skipped: %s", campaign_id, exc)
                results[campaign_id] = {"skipped": "budget"}
            except XApiError as exc:
                logger.warning("Listening campaign %s X error: %s", campaign_id, exc)
                results[campaign_id] = {"skipped": "x_error"}
    return results


async def _poll_mentions() -> dict:
    async with AsyncSessionLocal() as db:
        try:
            return await poll_mentions(db)
        except XApiError as exc:
            logger.warning("Listening mentions poll skipped: %s", exc)
            return {"skipped": str(exc)}


async def _purge() -> dict:
    async with AsyncSessionLocal() as db:
        return await purge_listening_data(db)


@celery_app.task(name="workers.listening_worker.poll_all_campaigns")
def poll_all_campaigns():
    return _run(_poll_all_campaigns())


@celery_app.task(name="workers.listening_worker.poll_outreach_mentions")
def poll_outreach_mentions():
    return _run(_poll_mentions())


@celery_app.task(name="workers.listening_worker.purge_listening")
def purge_listening():
    return _run(_purge())
