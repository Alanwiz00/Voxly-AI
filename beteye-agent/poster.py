"""X (Twitter) posting and metrics via Tweepy OAuth 1.0a."""
import logging
import os
import tweepy

log = logging.getLogger("beteye.poster")

_client: tweepy.Client | None = None
_v1_api: tweepy.API | None = None

_REQUIRED_CREDS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


def validate_credentials() -> bool:
    """
    Check all four X credentials are present and non-empty.
    Call at startup — posts will 403 silently otherwise.
    """
    missing = [k for k in _REQUIRED_CREDS if not os.environ.get(k)]
    if missing:
        log.error(
            f"[poster] Missing X credentials: {missing}. "
            "Posting will fail. Set these in .env and ensure the Twitter app has "
            "Read+Write permissions, then regenerate Access Token + Secret."
        )
        return False
    log.info("[poster] X credentials present — OAuth 1.0a ready")
    return True


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


def _get_v1_api() -> tweepy.API:
    """Tweepy v1.1 API — required for media upload (not available in v2 Client)."""
    global _v1_api
    if _v1_api is None:
        auth = tweepy.OAuth1UserHandler(
            os.environ["X_API_KEY"],
            os.environ["X_API_SECRET"],
            os.environ["X_ACCESS_TOKEN"],
            os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        _v1_api = tweepy.API(auth)
    return _v1_api


def upload_media(image_path: str) -> str | None:
    """
    Upload an image to X/Twitter and return the media_id string.
    Uses v1.1 API (chunked upload). Returns None on failure — post goes out without image.
    """
    try:
        media = _get_v1_api().media_upload(filename=image_path)
        log.info(f"[poster] Media uploaded: {media.media_id}")
        return str(media.media_id)
    except tweepy.errors.Forbidden:
        log.warning(
            "[poster] Media upload 403 — Twitter app needs Read+Write permissions. "
            "Update permissions in Developer Portal then regenerate Access Token + Secret."
        )
        return None
    except Exception as e:
        log.warning(f"[poster] Media upload failed: {e}")
        return None


def post_tweet(text: str, reply_to_id: str | None = None, media_id: str | None = None) -> str:
    """Post a tweet and return the tweet ID."""
    kwargs: dict = {"text": text[:4000]}  # X Premium Basic limit
    if reply_to_id:
        kwargs["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    if media_id:
        # Tweepy v4: media_ids is a direct list param — NOT media={"media_ids": [...]}
        kwargs["media_ids"] = [media_id]
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
