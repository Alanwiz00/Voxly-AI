import json
from openai import AsyncOpenAI
from core.config import settings
from services.sentiment import get_openai
from services.formatter import format_content, sanitize_body, FormattedContent

PLATFORM_INSTRUCTIONS = {
    "twitter": (
        "Twitter/X (X Premium). "
        "Post ideas: aim for 400-800 characters — substantive but focused, not a wall of text. "
        "Long-form: up to 2,500 characters. Articles: up to 3,000 characters. "
        "Follow the FORMAT TEMPLATE in the task exactly — structure, line breaks, and length. "
        "Every fact must be traceable to the source material. No invented context. "
        "Plain text only — no emojis, no hashtags, no markdown symbols like * or **. "
        "NEVER mention a media outlet, publication, or website by name. "
        "NEVER ask a question. Declarative statements only. Never start with 'I'."
    ),
    "instagram": (
        "Instagram. The first line must stop the scroll before 'more' is tapped. "
        "Use line breaks for readability. Use emojis very sparingly — 1-2 max, only when they add meaning. "
        "End with a question to drive comments. Suggest 10-15 targeted hashtags."
    ),
    "facebook": (
        "Facebook. Conversational and personal tone. Medium length (100-300 words). "
        "Tell a short story or share an insight. End with a clear call to action or question. "
        "Avoid overly salesy language. Minimal emojis — use only when natural."
    ),
    "telegram": (
        "Telegram channel. Readers opted in — they want depth and value. "
        "Use markdown (*bold*, _italic_) for structure. Can be longer. "
        "Be direct, informative, and opinionated. End with a key takeaway. "
        "No emojis unless the persona explicitly uses them."
    ),
}

CONTENT_TYPE_INSTRUCTIONS = {
    "idea": (
        "Generate {count} distinct post ideas. Each must have a different angle, tone, or hook. "
        "Vary approaches: use data, story, question, contrarian take, list, or analogy. "
        "Each idea should be ready to post with minimal editing."
    ),
    "long_form": (
        "Write one complete, well-structured long-form post. "
        "Include: a strong opening hook, 3-5 substantive points with supporting detail, and a memorable closing line."
    ),
    "thread": (
        "Write a Twitter thread of 8-12 tweets. "
        "Tweet 1: bold hook that makes people want to read on. "
        "Tweets 2-N: one clear idea per tweet, build progressively. "
        "Final tweet: strong takeaway or call to action."
    ),
    "article": (
        "Write a complete article with: a compelling title, intro paragraph, "
        "3-5 sections each with a subheading, and a conclusion with actionable takeaways."
    ),
}


_NO_SOURCE_FALLBACK = (
    "No verified source data available. Write about established principles and well-known "
    "fundamentals only. Do NOT invent or estimate statistics, percentages, specific dates, "
    "revenue figures, or projections. Use hedging language for any uncertain claims "
    "(e.g., 'analysts broadly note', 'industry consensus holds')."
)


def _build_system_prompt(platform: str, persona_context: str) -> str:
    platform_info = PLATFORM_INSTRUCTIONS.get(platform, "a social media platform")
    persona_block = f"\n\nUser's content persona:\n{persona_context}" if persona_context else ""
    return (
        f"You are an expert social media strategist and copywriter. "
        f"You write for {platform_info}{persona_block}\n\n"
        "Rules:\n"
        "- Match the user's established voice, tone, and niche exactly\n"
        "- Never use filler phrases like 'In today's world', 'It's important to note', or 'Dive into'\n"
        "- Be specific — cite numbers and examples from the SOURCE MATERIAL provided; never invent them\n"
        "- Write like a human, not a marketing bot\n"
        "- No emojis on Twitter/X. On other platforms use at most 1-2 only when they add real meaning\n"
        "- Always return valid JSON as instructed\n\n"
        "ACCURACY RULES — never break these:\n"
        "- Every specific statistic, percentage, date, or figure must come from the SOURCE MATERIAL\n"
        "- If source material has no specific data, use hedging language — never state a bare figure\n"
        "- Do not invent timelines, projections, or outcomes\n"
        "- Temporal claims ('this year', 'recently', 'last quarter') must reference a date from the sources\n"
        "- Clearly signal analysis vs. cited fact: 'according to sources' vs. 'in my view'\n\n"
        "STYLE RULES — human writing only:\n"
        "- Never use em-dashes (the — character) or en-dashes (the – character). Use a comma, period, or plain hyphen instead\n"
        "- Never use double hyphens (--)\n"
        "- Use contractions naturally: don't, it's, we're, they've\n"
        "- Vary sentence length. Short punchy lines. Followed by a longer explanatory one when needed\n"
        "- Plain text only. No markdown bold (**text**) or italic (*text*)\n"
        "- Never open with 'I', 'In today's', 'It's important to note', or 'As a [role]'"
    )


async def generate_post_ideas(
    topic: str,
    platform: str,
    persona_context: str,
    sentiment_context: str,
    count: int = 3,
) -> list[dict]:
    system = _build_system_prompt(platform, persona_context)
    user_msg = (
        f"Topic: {topic}\n\n"
        f"SOURCE MATERIAL (only use facts and figures from here):\n{sentiment_context or _NO_SOURCE_FALLBACK}\n\n"
        f"Task: {CONTENT_TYPE_INSTRUCTIONS['idea'].format(count=count)}\n\n"
        f"Return JSON:\n"
        f'{{"ideas": [{{'
        f'"title": "short descriptive title",'
        f'"hook": "the opening line",'
        f'"body": "full post text",'
        f'"cta": "call to action (1 sentence)",'
        f'"hashtags": ["tag1", "tag2"],'
        f'"score": 8,'
        f'"score_reason": "why this will perform well"'
        f"}}]}}"
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.85,
        max_tokens=2048,
    )

    data = json.loads(response.choices[0].message.content)
    results = []
    for idea in data.get("ideas", []):
        body = idea.get("body", "")
        hashtags = idea.get("hashtags", [])
        formatted = format_content(platform, body, "idea", hashtags)
        formatted.meta.update({
            "title": idea.get("title", ""),
            "hook": idea.get("hook", ""),
            "cta": idea.get("cta", ""),
            "score": idea.get("score", 0),
            "score_reason": idea.get("score_reason", ""),
            "hashtags": hashtags,
        })
        results.append(formatted)
    return results


async def generate_long_form(
    topic: str,
    platform: str,
    content_type: str,
    persona_context: str,
    sentiment_context: str,
) -> FormattedContent:
    system = _build_system_prompt(platform, persona_context)
    instruction = CONTENT_TYPE_INSTRUCTIONS.get(content_type, CONTENT_TYPE_INSTRUCTIONS["long_form"])

    if content_type == "thread":
        json_format = (
            '{"title": "...", '
            '"tweets": ["tweet 1 text (no numbering, just the text)", "tweet 2 text", ...], '
            '"score": 8, "score_reason": "..."}'
        )
    else:
        json_format = '{"title": "...", "body": "...", "hashtags": ["..."], "score": 8, "score_reason": "..."}'

    user_msg = (
        f"Topic: {topic}\n\n"
        f"SOURCE MATERIAL (only use facts and figures from here):\n{sentiment_context or _NO_SOURCE_FALLBACK}\n\n"
        f"Task: {instruction}\n\n"
        f"Return JSON:\n{json_format}"
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.75,
        max_tokens=4096,
    )

    data = json.loads(response.choices[0].message.content)

    if content_type == "thread" and "tweets" in data:
        tweets = data["tweets"]
        numbered = [f"{i+1}/{len(tweets)} {t}" for i, t in enumerate(tweets)]
        body = "\n\n---\n\n".join(numbered)
        hashtags = data.get("hashtags", [])
    else:
        body = data.get("body", "")
        hashtags = data.get("hashtags", [])

    formatted = format_content(platform, body, content_type, hashtags)
    formatted.meta.update({
        "title": data.get("title", ""),
        "score": data.get("score", 0),
        "score_reason": data.get("score_reason", ""),
        "hashtags": hashtags,
    })
    return formatted


async def generate_for_all_platforms(
    topic: str,
    content_type: str,
    persona_context: str,
    sentiment_context: str,
) -> dict[str, FormattedContent]:
    """Generate content adapted for all four platforms in one call."""
    platforms = ["twitter", "instagram", "facebook", "telegram"]
    system = (
        f"You are an expert social media strategist. "
        f"Given a topic, write platform-native content for all four major platforms in one response.\n\n"
        f"User persona:\n{persona_context or 'Not specified.'}\n\n"
        "Rules: each platform version must feel native — not copy-pasted. "
        "Match each platform's tone, format, and length expectations exactly. "
        "No emojis on Twitter/X. Other platforms: at most 1-2 emojis, only when they add meaning."
    )
    user_msg = (
        f"Topic: {topic}\n\n"
        f"SOURCE MATERIAL (only use facts and figures from here):\n{sentiment_context or _NO_SOURCE_FALLBACK}\n\n"
        f"Content type: {content_type}\n\n"
        "Return JSON with a key for each platform:\n"
        '{"twitter": {"body": "...", "score": 8}, '
        '"instagram": {"body": "...", "hashtags": [...], "score": 8}, '
        '"facebook": {"body": "...", "score": 8}, '
        '"telegram": {"body": "...", "score": 8}}'
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=4096,
    )

    data = json.loads(response.choices[0].message.content)
    results = {}
    for platform in platforms:
        p_data = data.get(platform, {})
        body = p_data.get("body", "")
        hashtags = p_data.get("hashtags", [])
        formatted = format_content(platform, body, content_type, hashtags)
        formatted.meta.update({
            "score": p_data.get("score", 0),
            "hashtags": hashtags,
        })
        results[platform] = formatted
    return results


async def generate_reusable_ideas(
    topic: str,
    persona_context: str,
    sentiment_context: str,
    count: int = 3,
) -> list[FormattedContent]:
    """Platform-agnostic short post ideas, reusable across any platform."""
    persona_block = f"\n\nUser's content persona:\n{persona_context}" if persona_context else ""
    system = (
        "You are an expert content strategist. "
        "Write platform-agnostic content that captures the core message powerfully. "
        "Content must be reusable — adaptable to Twitter, Instagram, Facebook, or Telegram later. "
        "Focus on substance: compelling narrative, key insights, and facts grounded in the source material."
        f"{persona_block}\n\n"
        "Rules:\n"
        "- No filler phrases like 'In today's world' or 'It's important to note'\n"
        "- Only cite specific numbers, statistics, or dates that appear in the SOURCE MATERIAL\n"
        "- If no figures are in the source material, describe patterns and insights without inventing data\n"
        "- Write like a knowledgeable human, not a marketing bot\n"
        "- Always return valid JSON as instructed\n\n"
        "ACCURACY RULES:\n"
        "- Never invent statistics, percentages, revenue figures, or dates\n"
        "- Never state a specific figure as fact unless it is in the source material\n"
        "- Use hedging language when source data is absent: 'analysts note', 'commonly observed', 'broadly cited'\n\n"
        "STYLE RULES:\n"
        "- Never use em-dashes (—) or en-dashes (–). Comma, period, or plain hyphen only\n"
        "- No double hyphens (--)\n"
        "- Use contractions: don't, it's, we're, they've\n"
        "- Vary sentence length deliberately\n"
        "- Plain text. No markdown bold (**) or italic (*)"
    )
    user_msg = (
        f"Topic: {topic}\n\n"
        f"SOURCE MATERIAL (only use facts and figures from here):\n{sentiment_context or _NO_SOURCE_FALLBACK}\n\n"
        f"Task: Generate {count} distinct reusable short post ideas. Each must have a different angle, tone, or hook. "
        "Vary approaches: data, story, question, contrarian take, list, or analogy. "
        "Each should be 150-300 words — substantive enough to stand alone, concise enough to adapt.\n\n"
        f"Return JSON:\n"
        f'{{"ideas": [{{'
        f'"title": "short descriptive title",'
        f'"hook": "the opening line",'
        f'"body": "full post text",'
        f'"cta": "call to action (1 sentence)",'
        f'"score": 8,'
        f'"score_reason": "why this will perform well"'
        f"}}]}}"
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=2048,
    )

    data = json.loads(response.choices[0].message.content)
    results = []
    for idea in data.get("ideas", []):
        results.append(FormattedContent(
            platform="general",
            content_type="idea",
            body=sanitize_body(idea.get("body", "")),
            meta={
                "title": idea.get("title", ""),
                "hook": idea.get("hook", ""),
                "cta": idea.get("cta", ""),
                "score": idea.get("score", 0),
                "score_reason": idea.get("score_reason", ""),
            },
        ))
    return results


async def generate_reusable_longform(
    topic: str,
    persona_context: str,
    sentiment_context: str,
) -> FormattedContent:
    """Platform-agnostic long-form post, reusable and adaptable to any platform."""
    persona_block = f"\n\nUser's content persona:\n{persona_context}" if persona_context else ""
    system = (
        "You are an expert content writer. "
        "Write a comprehensive, platform-agnostic long-form post — the definitive piece on this topic. "
        "No platform-specific formatting. Focus on thorough, well-structured, engaging content."
        f"{persona_block}\n\n"
        "Rules:\n"
        "- Strong opening hook\n"
        "- 3-5 substantive points grounded in the source material provided\n"
        "- Memorable closing line\n"
        "- No filler phrases, no corporate speak\n"
        "- Write like a knowledgeable human\n"
        "- Always return valid JSON as instructed\n\n"
        "ACCURACY RULES:\n"
        "- Every specific statistic, percentage, date, or figure must come from the SOURCE MATERIAL\n"
        "- If source material has no specific data, use hedging language — never state a bare figure\n"
        "- Do not invent timelines, projections, or outcomes\n"
        "- Temporal claims must reference a date from the source material, not from general knowledge\n\n"
        "STYLE RULES:\n"
        "- Never use em-dashes (—) or en-dashes (–). Comma, period, or plain hyphen only\n"
        "- No double hyphens (--)\n"
        "- Use contractions: don't, it's, we're, they've\n"
        "- Vary sentence length deliberately\n"
        "- Plain text. No markdown bold (**) or italic (*)"
    )
    user_msg = (
        f"Topic: {topic}\n\n"
        f"SOURCE MATERIAL (only use facts and figures from here):\n{sentiment_context or _NO_SOURCE_FALLBACK}\n\n"
        "Task: Write one complete, platform-agnostic long-form post (500-800 words). "
        "Structure: strong hook → 3-5 substantive points → memorable close.\n\n"
        'Return JSON: {"title": "...", "body": "...", "score": 8, "score_reason": "..."}'
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.65,
        max_tokens=4096,
    )

    data = json.loads(response.choices[0].message.content)
    return FormattedContent(
        platform="general",
        content_type="long_form",
        body=sanitize_body(data.get("body", "")),
        meta={
            "title": data.get("title", ""),
            "score": data.get("score", 0),
            "score_reason": data.get("score_reason", ""),
        },
    )


async def adapt_to_platform(
    content: str,
    title: str,
    platform: str,
    persona_context: str,
) -> FormattedContent:
    """Rewrite general content natively for a specific platform."""
    platform_info = PLATFORM_INSTRUCTIONS.get(platform, "a social media platform")
    persona_block = f"\n\nUser's content persona:\n{persona_context}" if persona_context else ""
    system = (
        f"You are an expert social media strategist. "
        f"Adapt the provided content for {platform_info}{persona_block}\n\n"
        "Rules:\n"
        "- Preserve all core ideas and insights\n"
        "- Reformat natively — match the platform's tone, length, and structure exactly\n"
        "- Add platform-appropriate elements (hashtags for Instagram, numbered tweets for Twitter threads, etc.)\n"
        "- Never use filler phrases\n"
        "- Write like a human, not a marketing bot\n"
        "- No emojis on Twitter/X. Other platforms: at most 1-2, only when they add real meaning\n"
        "- Always return valid JSON as instructed"
    )
    user_msg = (
        f"Original content:\n{content}\n\n"
        f"Adapt this natively for {platform}. "
        + (
            'Return JSON: {"body": "...", "hashtags": ["tag1", "tag2"]}'
            if platform == "instagram"
            else 'Return JSON: {"body": "..."}'
        )
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=2048,
    )

    data = json.loads(response.choices[0].message.content)
    body = data.get("body", content)
    hashtags = data.get("hashtags", [])
    formatted = format_content(platform, body, "long_form", hashtags)
    formatted.meta.update({"title": title, "hashtags": hashtags})
    return formatted


async def re_edit_content(original: str, platform: str, instruction: str, persona_context: str) -> str:
    system = _build_system_prompt(platform, persona_context)
    user_msg = (
        f"Original content:\n{original}\n\n"
        f"Edit instruction: {instruction}\n\n"
        "Apply the edit while preserving the author's voice and style. "
        "Only change what the instruction asks for — nothing else. "
        'Return JSON: {"body": "..."}'
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.6,
    )

    data = json.loads(response.choices[0].message.content)
    return sanitize_body(data.get("body", original))
