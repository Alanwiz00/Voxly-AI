"""X API v2 client for listening: recent counts, recent search, user lookup, mentions.

Read-only by design: outreach replies are posted by a person in X's own composer,
never through the API (X's automation rules, and API posts with links cost $0.20).

Pay-per-use bills per resource returned, so every call is priced up front
(worst case) against the monthly budgets and refused if it could break them; the
actual billed resources are then written to x_api_usage.
"""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.listening import ListeningCampaign, XApiUsage


class XApiError(Exception):
    pass


class XBudgetExceeded(XApiError):
    pass


class XPaceLimit(XBudgetExceeded):
    """The campaign has spent its even share of the month so far; it resumes as time passes."""


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def pace_allowance(monthly_budget: float, now: datetime | None = None) -> float:
    """What a campaign may have spent by now if its budget is spread evenly over the month.

    Time-based rather than per calendar day, so spending isn't front-loaded at
    midnight UTC (1am in Lagos, hours before the matches people talk about).
    Unspent budget carries forward automatically.
    """
    now = now or datetime.now(timezone.utc)
    start = _month_start(now)
    end = (start + timedelta(days=32)).replace(day=1)
    return monthly_budget * (now - start) / (end - start)


async def month_spend(db: AsyncSession, campaign_id: int | None = None) -> float:
    query = select(func.coalesce(func.sum(XApiUsage.cost_usd), 0.0)).where(XApiUsage.created_at >= _month_start())
    if campaign_id is not None:
        query = query.where(XApiUsage.campaign_id == campaign_id)
    return float((await db.execute(query)).scalar() or 0.0)


class XClient:
    def __init__(self, db: AsyncSession, campaign: ListeningCampaign | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.db = db
        self.campaign = campaign
        self._transport = transport

    async def _guard(self, worst_case_usd: float, paced: bool = False) -> None:
        if not settings.X_BEARER_TOKEN:
            raise XApiError("X_BEARER_TOKEN is not set")
        if await month_spend(self.db) + worst_case_usd > settings.LISTENING_MONTHLY_BUDGET_USD:
            raise XBudgetExceeded("Monthly X budget reached for all listening")
        if not self.campaign:
            return
        spent = await month_spend(self.db, self.campaign.id)
        if spent + worst_case_usd > self.campaign.monthly_budget_usd:
            raise XBudgetExceeded(f"Monthly X budget reached for campaign {self.campaign.id}")
        # Searches are the discretionary spend, so only they wait for the pace to catch up.
        # One search may run while spend is at or under the even share, so each can overshoot
        # by at most its own worst case; the monthly cap above still holds.
        allowance = pace_allowance(self.campaign.monthly_budget_usd)
        if paced and spent > allowance:
            raise XPaceLimit(
                f"Campaign {self.campaign.id} is ahead of its budget pace "
                f"(${spent:.2f} spent, ${allowance:.2f} allowed so far this month); it resumes as the month goes on"
            )

    async def _get(self, path: str, params: dict, endpoint: str, worst_case_usd: float, paced: bool = False) -> dict:
        await self._guard(worst_case_usd, paced)
        async with httpx.AsyncClient(
            base_url=settings.X_API_BASE_URL,
            headers={"Authorization": f"Bearer {settings.X_BEARER_TOKEN}"},
            timeout=15.0,
            transport=self._transport,
        ) as client:
            resp = await client.get(path, params=params)
        if resp.status_code == 429:
            raise XApiError("X rate limit hit; try again later")
        if resp.status_code >= 400:
            raise XApiError(f"X returned {resp.status_code} on {endpoint}")
        return resp.json()

    async def _record(self, endpoint: str, resources: int, cost_usd: float) -> None:
        self.db.add(XApiUsage(
            campaign_id=self.campaign.id if self.campaign else None,
            endpoint=endpoint,
            resources=resources,
            cost_usd=round(cost_usd, 6),
        ))
        await self.db.flush()

    async def count_recent(self, query: str) -> int:
        """Matching posts over the last 7 days. Billed per request, so it sizes a query cheaply."""
        data = await self._get(
            "/2/tweets/counts/recent", {"query": query, "granularity": "day"},
            "counts_recent", settings.X_PRICE_COUNTS_REQUEST,
        )
        await self._record("counts_recent", 1, settings.X_PRICE_COUNTS_REQUEST)
        return int(data.get("meta", {}).get("total_tweet_count", 0))

    async def search_recent(self, query: str, since_id: str | None, max_results: int) -> tuple[list[dict], str | None]:
        """New posts matching the query. No expansions, so no user objects are billed here."""
        max_results = max(10, min(100, max_results))
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,lang,author_id,conversation_id",
        }
        if since_id:
            params["since_id"] = since_id
        data = await self._get(
            "/2/tweets/search/recent", params, "search_recent", max_results * settings.X_PRICE_POST_READ, paced=True,
        )
        posts = data.get("data", []) or []
        await self._record("search_recent", len(posts), len(posts) * settings.X_PRICE_POST_READ)
        return posts, data.get("meta", {}).get("newest_id")

    async def users_by_ids(self, ids: list[str]) -> dict[str, dict]:
        """Profiles for the posts that passed the AI check only."""
        if not ids:
            return {}
        ids = ids[:100]
        data = await self._get(
            "/2/users", {"ids": ",".join(ids), "user.fields": "description,location,protected,username"},
            "users_lookup", len(ids) * settings.X_PRICE_USER_READ,
        )
        users = data.get("data", []) or []
        await self._record("users_lookup", len(users), len(users) * settings.X_PRICE_USER_READ)
        return {u["id"]: u for u in users}

    async def mentions(self, user_id: str, since_id: str | None) -> tuple[list[dict], str | None]:
        """Replies and mentions of the outreach account, to track replies and opt-outs."""
        params = {"max_results": 100, "tweet.fields": "created_at,author_id,referenced_tweets"}
        if since_id:
            params["since_id"] = since_id
        data = await self._get(
            f"/2/users/{user_id}/mentions", params, "mentions", 100 * settings.X_PRICE_POST_READ,
        )
        posts = data.get("data", []) or []
        await self._record("mentions", len(posts), len(posts) * settings.X_PRICE_POST_READ)
        return posts, data.get("meta", {}).get("newest_id")
