"""One LLM call per surviving post: what does this person want, and is it safe to reply?

Fails closed: any error, unknown intent, harm or age signal, or low confidence means
the post is dropped. The AI only classifies; it never writes outreach copy.
"""
import json
import logging

from services.llm import llm_complete

logger = logging.getLogger(__name__)

ELIGIBLE_INTENTS = {"seeking_live_alerts", "seeking_tips", "tipster_complaint", "odds_discussion"}
MIN_CONFIDENCE = 0.7

_SYSTEM = (
    "You screen public X posts for a football live-alerts app before anyone replies to them. "
    "Classify the post. Be strict: if a post shows any sign of gambling harm (losing control, "
    "chasing losses, money trouble from betting, wanting to quit, distress) or any sign the author "
    "is under 18, list it. Return valid JSON only."
)

_SCHEMA = (
    '{"intent": "seeking_live_alerts | seeking_tips | tipster_complaint | odds_discussion | harm | unrelated", '
    '"harm_signals": ["exact words that show gambling harm"], '
    '"age_signals": ["exact words that suggest the author is under 18"], '
    '"market": "ISO country code the author is likely in, from language, slang or teams, or unknown", '
    '"teams": ["football teams named in the post"], '
    '"confidence": 0.0}'
)


def _drop(reason: str, **extra) -> dict:
    return {"eligible": False, "reason": reason, **extra}


async def classify_post(text: str) -> dict:
    try:
        raw, _tokens = await llm_complete(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Post:\n{text}\n\nReturn JSON:\n{_SCHEMA}"},
            ],
            temperature=0.0,
            max_tokens=300,
        )
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("Listening classifier failed, dropping post: %r", exc)
        return _drop("classifier_error")

    verdict = {
        "intent": str(data.get("intent", "")),
        "harm_signals": [str(s) for s in data.get("harm_signals") or []],
        "age_signals": [str(s) for s in data.get("age_signals") or []],
        "market": str(data.get("market") or "unknown").upper()[:8],
        "teams": [str(t) for t in data.get("teams") or []][:4],
        "confidence": float(data.get("confidence") or 0.0),
    }
    if verdict["harm_signals"] or verdict["intent"] == "harm":
        return _drop("ai_harm_signal", **verdict)
    if verdict["age_signals"]:
        return _drop("ai_age_signal", **verdict)
    if verdict["intent"] not in ELIGIBLE_INTENTS:
        return _drop("not_relevant", **verdict)
    if verdict["confidence"] < MIN_CONFIDENCE:
        return _drop("low_confidence", **verdict)
    return {"eligible": True, "reason": None, **verdict}
