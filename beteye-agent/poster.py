"""X (Twitter) posting and metrics via Tweepy OAuth 1.0a."""
import logging
import os
import tweepy

log = logging.getLogger("beteye.poster")

_client: tweepy.Client | None = None


def _get_client() -> tweepy.Client:
    global _client
    if _client is None:
        _client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
    return _client


def post_tweet(text: str, reply_to_id: str | None = None) -> str:
    """Post a tweet and return the tweet ID. Optionally post as a reply."""
    kwargs: dict = {"text": text[:280]}
    if reply_to_id:
        kwargs["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    response = _get_client().create_tweet(**kwargs)
    return str(response.data["id"])


def get_tweet_metrics(tweet_id: str) -> dict | None:
    """
    Fetch public engagement metrics for a tweet we posted.
    Returns None if the request fails (e.g. insufficient API tier).
    """
    try:
        response = _get_client().get_tweet(
            tweet_id,
            tweet_fields=["public_metrics"],
        )
        if response.data and response.data.public_metrics:
            return dict(response.data.public_metrics)
    except Exception as e:
        log.debug(f"get_tweet_metrics({tweet_id}) failed: {e}")
    return None
