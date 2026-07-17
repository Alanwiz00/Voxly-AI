import re
from dataclasses import dataclass

# Character limits only apply to short posts (content_type="idea")
LONG_FORM_TYPES = {"long_form", "thread", "article"}

# Characters that make AI content feel robotic — replace with natural equivalents
_EM_DASH_SPACED   = re.compile(r'\s*—\s*')   # em-dash (with or without surrounding spaces)
_EN_DASH_SPACED   = re.compile(r'\s*–\s*')   # en-dash
_DOUBLE_HYPHEN    = re.compile(r'--+')        # double/triple hyphen
_ELLIPSIS_CHAR    = re.compile(r'…')          # unicode ellipsis → three dots
_CURLY_OPEN_DBL   = re.compile(r'[“„]')   # " " → "
_CURLY_CLOSE_DBL  = re.compile(r'[”‟]')   # " " → "
_CURLY_OPEN_SGL   = re.compile(r'[‘‚]')   # ' ‚ → '
_CURLY_CLOSE_SGL  = re.compile(r'[’‛]')   # ' ‛ → '
_MARKDOWN_BOLD    = re.compile(r'\*\*(.+?)\*\*')     # **text** → text
_MARKDOWN_ITALIC  = re.compile(r'\*(.+?)\*')         # *text* → text
_EXCESS_NEWLINES  = re.compile(r'\n{3,}')            # 3+ newlines → 2


def sanitize_body(text: str) -> str:
    """Strip AI-isms: em-dashes, curly quotes, markdown bold/italic, excess whitespace."""
    text = _EM_DASH_SPACED.sub(', ', text)
    text = _EN_DASH_SPACED.sub(', ', text)
    text = _DOUBLE_HYPHEN.sub('-', text)
    text = _ELLIPSIS_CHAR.sub('...', text)
    text = _CURLY_OPEN_DBL.sub('"', text)
    text = _CURLY_CLOSE_DBL.sub('"', text)
    text = _CURLY_OPEN_SGL.sub("'", text)
    text = _CURLY_CLOSE_SGL.sub("'", text)
    text = _MARKDOWN_BOLD.sub(r'\1', text)
    text = _MARKDOWN_ITALIC.sub(r'\1', text)
    text = _EXCESS_NEWLINES.sub('\n\n', text)
    return text.strip()

# Per-content-type character limits for Twitter (X Premium)
TWITTER_LIMITS = {
    "idea": 800,
    "long_form": 2500,
    "article": 3000,
}

PLATFORM_LIMITS = {
    "instagram": 2200,
    "facebook": 63206,
    "telegram": 4096,
}


@dataclass
class FormattedContent:
    platform: str
    content_type: str
    body: str
    meta: dict


def _split_thread(text: str, char_limit: int = 270) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    tweets: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= char_limit:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                tweets.append(current)
            if len(sentence) > char_limit:
                for i in range(0, len(sentence), char_limit):
                    tweets.append(sentence[i:i + char_limit])
                current = ""
            else:
                current = sentence
    if current:
        tweets.append(current)
    return [f"{i+1}/{len(tweets)} {t}" for i, t in enumerate(tweets)]


def format_for_twitter(content: str, content_type: str) -> FormattedContent:
    if content_type == "thread":
        # content is pre-formatted as "1/N text\n\n---\n\n2/N text..." by the generator
        tweets = [t.strip() for t in content.split("\n\n---\n\n") if t.strip()]
        return FormattedContent(
            platform="twitter",
            content_type="thread",
            body=content,
            meta={"tweet_count": len(tweets), "tweets": tweets},
        )
    limit = TWITTER_LIMITS.get(content_type)
    if limit and len(content) > limit:
        content = content[:limit - 3] + "..."
    return FormattedContent(platform="twitter", content_type=content_type, body=content, meta={})


def format_for_instagram(content: str, content_type: str, hashtags: list[str] | None = None) -> FormattedContent:
    if content_type in LONG_FORM_TYPES:
        # Long-form: no caption limit, append hashtags without truncating
        tag_block = "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in (hashtags or [])[:30])
        body = content + (tag_block if hashtags else "")
        return FormattedContent(platform="instagram", content_type=content_type, body=body, meta={"hashtags": hashtags or []})
    # Short post: respect 2200 char caption limit
    tag_block = "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in (hashtags or [])[:30]) if hashtags else ""
    full = (content[:2200] + tag_block)[:2200]
    return FormattedContent(platform="instagram", content_type="post", body=full, meta={"hashtags": hashtags or []})


def format_for_facebook(content: str, content_type: str) -> FormattedContent:
    # Facebook limit is 63k chars — effectively unlimited for any content we generate
    return FormattedContent(platform="facebook", content_type=content_type, body=content, meta={})


def format_for_telegram(content: str, content_type: str) -> FormattedContent:
    if content_type in LONG_FORM_TYPES:
        # Long-form: no truncation; Telegram supports long messages via scrolling
        return FormattedContent(platform="telegram", content_type=content_type, body=content, meta={})
    # Short post: respect 4096 char single-message limit
    return FormattedContent(platform="telegram", content_type="post", body=content[:4096], meta={})


def format_content(
    platform: str,
    content: str,
    content_type: str,
    hashtags: list[str] | None = None,
) -> FormattedContent:
    content = sanitize_body(content)
    dispatch = {
        "twitter": lambda: format_for_twitter(content, content_type),
        "instagram": lambda: format_for_instagram(content, content_type, hashtags),
        "facebook": lambda: format_for_facebook(content, content_type),
        "telegram": lambda: format_for_telegram(content, content_type),
    }
    fn = dispatch.get(platform)
    if fn is None:
        return FormattedContent(platform=platform, content_type=content_type, body=content, meta={})
    return fn()
