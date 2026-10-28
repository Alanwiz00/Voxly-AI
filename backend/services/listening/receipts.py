"""Proof for drafts: a finished, winning BetEye alert on a match the post mentions.

BetEye only returns alerts whose match has finished, so outreach never gives away
live paid signals. Optional: without BetEye configured, only no-proof templates draft.
"""
import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def receipts_configured() -> bool:
    return bool(settings.BETEYE_API_URL and settings.BETEYE_OUTREACH_KEY)


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> list[dict]:
    resp = await client.get(path, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def find_proof(teams: list[str], transport: httpx.AsyncBaseTransport | None = None) -> dict | None:
    """Most recent winning alert on a recent fixture involving one of these teams."""
    if not receipts_configured() or not teams:
        return None
    try:
        async with httpx.AsyncClient(
            base_url=settings.BETEYE_API_URL.rstrip("/"),
            headers={"X-BetEye-Outreach-Key": settings.BETEYE_OUTREACH_KEY},
            timeout=10.0,
            transport=transport,
        ) as client:
            for team in teams[:2]:
                fixtures = await _get(client, "/api/outreach/fixtures", {"q": team})
                for fixture in fixtures[:3]:
                    receipts = await _get(client, "/api/outreach/receipts", {"fixtureId": fixture["fixtureId"]})
                    wins = [r for r in receipts if r.get("outcome") == "WIN"]
                    if wins:
                        return max(wins, key=lambda r: r.get("firedAt") or "")
    except Exception as exc:
        logger.warning("BetEye receipts unavailable, drafting without proof: %r", exc)
    return None
