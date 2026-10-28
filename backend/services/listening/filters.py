"""Word-list checks that run before (and after) the AI check.

Harm and age signals are a hard drop: anyone showing gambling harm or signs of being
under 18 is never contacted. These lists are a starting point (English + Nigerian
Pidgin); campaigns add their own terms on top.
"""
import re

HARM_TERMS = [
    # loss of control
    "addicted", "addiction", "can't stop betting", "cant stop betting", "can't stop gambling",
    "gambling problem", "problem gambling", "compulsive", "chasing losses", "chasing my losses",
    "chase my losses", "quit betting", "quit gambling", "stop betting", "stop gambling",
    "self-exclusion", "self exclusion", "gamcare", "begambleaware", "gamblers anonymous",
    # money trouble
    "lost everything", "lost all my money", "lost my savings", "lost my salary", "rent money",
    "school fees", "borrowed money", "borrowed to bet", "loan app", "took a loan", "in debt",
    "debt", "broke", "bankrupt", "last money", "my last kobo", "last kobo",
    # Pidgin
    "i don lose", "don lose everything", "don lose all", "chop loss", "my money don finish",
    "salary don finish", "money don finish", "borrow money",
    # distress
    "suicide", "suicidal", "kill myself", "end it all", "depressed", "depression",
]

AGE_TERMS = [
    "jss1", "jss2", "jss3", "ss1", "ss2", "ss3", "jss", "secondary school", "high school",
    "waec", "neco", "my parents won't", "my mum will kill me", "underage",
]
_AGE_PATTERN = re.compile(r"\b(1[0-7])\s*(?:yo|y/o|yrs?|years?\s*old)\b|\bi'?m\s*(1[0-7])\b|\bage\s*(1[0-7])\b")

BANNED_CLAIMS = [
    "sure win", "sure odds", "sure banker", "guaranteed", "guarantee", "100% win", "100% sure",
    "risk-free", "risk free", "can't lose", "cannot lose", "recover your losses", "recover losses",
    "win back", "make money", "get rich", "easy money", "free money", "double your money",
    "quit your job", "fixed match", "fixed matches",
]

OPT_OUT_TERMS = [
    "stop", "unsubscribe", "leave me alone", "don't message", "dont message", "do not message",
    "don't dm", "dont dm", "stop messaging", "stop replying", "spam", "reported", "go away",
]

_NOT_WORD = r"[a-z0-9]"


def _normalise(text: str) -> str:
    return (text or "").lower().replace("’", "'").replace("‘", "'")


def find_terms(text: str, terms: list[str]) -> list[str]:
    """Terms that appear in text as whole words or phrases (case-insensitive)."""
    norm = _normalise(text)
    hits = []
    for term in terms:
        t = _normalise(term).strip()
        if t and re.search(rf"(?<!{_NOT_WORD}){re.escape(t)}(?!{_NOT_WORD})", norm):
            hits.append(term)
    return hits


def harm_signals(text: str, extra_terms: list[str] | None = None) -> list[str]:
    return find_terms(text, HARM_TERMS + list(extra_terms or []))


def age_signals(text: str) -> list[str]:
    hits = find_terms(text, AGE_TERMS)
    match = _AGE_PATTERN.search(_normalise(text))
    if match:
        hits.append(match.group(0))
    return hits


def banned_claims(text: str) -> list[str]:
    return find_terms(text, BANNED_CLAIMS)


def has_responsible_footer(text: str) -> bool:
    norm = _normalise(text)
    return "18+" in norm and "play responsibly" in norm


def is_opt_out(text: str) -> bool:
    return bool(find_terms(text, OPT_OUT_TERMS))


def matched_query_terms(text: str, x_query: str) -> list[str]:
    """Which plain words or quoted phrases from the X query appear in the post (for reviewers)."""
    phrases = re.findall(r'"([^"]+)"', x_query)
    words = [
        w for w in re.split(r'[\s()]+', re.sub(r'"[^"]+"', " ", x_query))
        if w and not w.startswith("-") and ":" not in w and w.upper() not in {"OR", "AND"}
    ]
    return find_terms(text, phrases + words)
