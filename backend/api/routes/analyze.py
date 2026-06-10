"""
Content performance analysis — takes post texts + engagement metrics,
returns green flags (amplify), red flags (avoid), and mode performance scores.
"""
import json
from fastapi import APIRouter
from pydantic import BaseModel
from api.deps import CurrentUser
from services.sentiment import get_openai
from core.config import settings

router = APIRouter(prefix="/analyze", tags=["analyze"])


class PostSample(BaseModel):
    text: str
    mode: str = ""
    impressions: int = 0
    likes: int = 0
    retweets: int = 0
    replies: int = 0


class PerformanceRequest(BaseModel):
    posts: list[PostSample]


def _eng_score(p: PostSample) -> float:
    return p.impressions + p.likes * 10 + p.retweets * 20 + p.replies * 15


@router.post("/performance")
async def analyze_performance(body: PerformanceRequest, current_user: CurrentUser):
    posts = [p for p in body.posts if p.text.strip()]
    if len(posts) < 3:
        return {"error": "Need at least 3 posts with metrics"}

    ranked  = sorted(posts, key=_eng_score, reverse=True)
    slice_n = max(1, len(ranked) // 3)

    top    = [{"text": p.text, "mode": p.mode, "score": round(_eng_score(p))} for p in ranked[:slice_n]]
    bottom = [{"text": p.text, "mode": p.mode, "score": round(_eng_score(p))} for p in ranked[-slice_n:]]

    # Per-mode averages
    from collections import defaultdict
    mode_scores: dict = defaultdict(list)
    for p in posts:
        if p.mode:
            mode_scores[p.mode].append(_eng_score(p))
    mode_avg = {m: round(sum(s) / len(s), 1) for m, s in mode_scores.items() if s}

    prompt = (
        "You are analyzing tweet performance for @beteye — a World Cup 2026 football news account on X (Twitter).\n\n"
        f"TOP PERFORMERS (highest engagement):\n{json.dumps(top, indent=2)}\n\n"
        f"LOWEST PERFORMERS:\n{json.dumps(bottom, indent=2)}\n\n"
        "Analyze what separates the winners from the losers. Look for:\n"
        "- Writing structure (do number-led posts win? short vs long?)\n"
        "- Specificity (named players/clubs/stats vs vague claims)\n"
        "- Tone (confident hot take vs neutral report vs question)\n"
        "- Hook type (what kind of opening drives clicks)\n"
        "- Ending (question vs statement — which drives replies?)\n\n"
        "Return JSON with CONCRETE, ACTIONABLE patterns — not vague advice:\n"
        "{\n"
        '  "green_flags": [\n'
        '    "Start with a specific number (goals, minutes, transfer fee)",\n'
        '    "... up to 6 patterns"\n'
        '  ],\n'
        '  "red_flags": [\n'
        '    "Avoid starting with a player name alone without context",\n'
        '    "... up to 6 patterns"\n'
        '  ],\n'
        '  "insight": "2-3 sentence plain English summary of the single biggest finding",\n'
        '  "best_hook_pattern": "The exact sentence structure that works best, e.g.: [NUMBER] [FACT]. [IMPLICATION]. [QUESTION]?"\n'
        "}"
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1024,
    )

    data = json.loads(response.choices[0].message.content)
    data["mode_performance"] = mode_avg
    data["posts_analyzed"]   = len(posts)
    return data
