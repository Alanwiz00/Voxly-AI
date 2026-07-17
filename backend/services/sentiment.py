from openai import AsyncOpenAI
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from core.config import settings

_client: AsyncOpenAI | None = None
_vader = SentimentIntensityAnalyzer()


def get_openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def vader_score(text: str) -> tuple[float, str]:
    scores = _vader.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return compound, label


async def summarize_and_analyze(topic_name: str, content: str, source_date: str | None = None) -> dict:
    date_hint = f"\nSource publication date (if known): {source_date}" if source_date else ""
    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_FAST_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict content analyst. Given raw web content about a topic, "
                    "return a JSON object with these exact keys:\n"
                    "  'summary': 2-3 sentence summary of the key points\n"
                    "  'key_themes': list of 3-5 theme strings\n"
                    "  'key_facts': list of up to 6 VERBATIM facts, statistics, or data points "
                    "extracted directly from the source — include the date/year if the source states it. "
                    "ONLY include facts that explicitly appear in the source text. "
                    "Leave this list EMPTY if no specific figures or verifiable facts are present.\n"
                    "  'article_date': the publication or event date from the content in ISO-8601 format "
                    "(YYYY-MM-DD or YYYY-MM), or null if not detectable\n"
                    "  'sentiment': one of: positive, negative, neutral\n"
                    "  'sentiment_reason': one sentence explaining the sentiment\n\n"
                    "CRITICAL: Never invent or infer facts not stated in the source."
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {topic_name}{date_hint}\n\nContent:\n{content[:5000]}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    import json
    try:
        data = json.loads(response.choices[0].message.content)
    except Exception:
        data = {
            "summary": content[:300],
            "key_themes": [],
            "key_facts": [],
            "article_date": source_date,
            "sentiment": "neutral",
            "sentiment_reason": "",
        }

    vader_compound, vader_label = vader_score(content)
    data["vader_score"] = vader_compound
    data["vader_label"] = vader_label
    return data


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = await get_openai().embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]
