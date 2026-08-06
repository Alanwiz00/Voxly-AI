"""
Multi-provider LLM client for text generation.

Priority: Groq (fast, cheap) → Gemini 2.0 Flash (fallback)

OpenAI is intentionally excluded here — it is kept only for:
  - extract_from_image() in ingest.py  (vision, requires GPT-4o)
  - get_embeddings() in sentiment.py   (text-embedding-3-small, $0.02/1M tokens)
"""

import logging
from openai import AsyncOpenAI
from core.config import settings

logger = logging.getLogger(__name__)

_groq_client: AsyncOpenAI | None = None
_gemini_client: AsyncOpenAI | None = None


def _groq() -> AsyncOpenAI | None:
    global _groq_client
    if settings.GROQ_API_KEY and _groq_client is None:
        _groq_client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    return _groq_client


def _gemini() -> AsyncOpenAI | None:
    global _gemini_client
    if settings.GEMINI_API_KEY and _gemini_client is None:
        _gemini_client = AsyncOpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _gemini_client


async def llm_complete(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> tuple[str, int]:
    """
    Send a chat completion request via Groq, falling back to Gemini.
    Returns (response_text, total_tokens).
    Both providers expose an OpenAI-compatible endpoint so no SDK swap is needed.
    """
    errors: list[str] = []

    # --- Groq (primary) ---
    groq = _groq()
    if groq:
        try:
            resp = await groq.chat.completions.create(
                model=settings.GROQ_GENERATION_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            tokens = resp.usage.total_tokens if resp.usage else 0
            return resp.choices[0].message.content, tokens
        except Exception as exc:
            errors.append(f"Groq: {exc}")
            logger.warning("Groq generation failed, falling back to Gemini: %s", exc)

    # --- Gemini (fallback) ---
    gemini = _gemini()
    if gemini:
        try:
            resp = await gemini.chat.completions.create(
                model=settings.GEMINI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            tokens = resp.usage.total_tokens if resp.usage else 0
            return resp.choices[0].message.content, tokens
        except Exception as exc:
            errors.append(f"Gemini: {exc}")
            logger.error("Gemini generation failed: %s", exc)

    if not errors:
        raise RuntimeError(
            "No LLM providers configured. Set GROQ_API_KEY and/or GEMINI_API_KEY in .env"
        )
    raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")
