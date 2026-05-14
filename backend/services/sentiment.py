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


async def summarize_and_analyze(topic_name: str, content: str) -> dict:
    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_FAST_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a content analyst. Given raw web content about a topic, "
                    "return a JSON object with keys: "
                    "'summary' (2-3 sentence summary of the key points), "
                    "'key_themes' (list of 3-5 theme strings), "
                    "'sentiment' (one of: positive, negative, neutral), "
                    "'sentiment_reason' (one sentence explaining the sentiment)."
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {topic_name}\n\nContent:\n{content[:4000]}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    import json
    try:
        data = json.loads(response.choices[0].message.content)
    except Exception:
        data = {"summary": content[:300], "key_themes": [], "sentiment": "neutral", "sentiment_reason": ""}

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
