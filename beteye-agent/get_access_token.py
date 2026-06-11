"""
Generate X (Twitter) access tokens for the Beteye account.

Run this once on your host machine (not inside Docker):
    pip install tweepy python-dotenv
    python beteye-agent/get_access_token.py

The script uses your app's API Key/Secret (from .env) and walks you through
the OAuth 1.0a PIN flow. Log in as the Beteye account when the browser opens.
Paste the resulting tokens into your .env file.
"""
import os
import sys
import webbrowser

try:
    import tweepy
except ImportError:
    sys.exit("Run: pip install tweepy")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

API_KEY    = os.environ.get("X_API_KEY")
API_SECRET = os.environ.get("X_API_SECRET")

if not API_KEY or not API_SECRET:
    sys.exit(
        "X_API_KEY and X_API_SECRET must be set in .env or as environment variables.\n"
        "These are the app credentials from developer.twitter.com — they stay the same."
    )

print("\n=== Beteye X Account Auth ===\n")
print(f"App key loaded: {API_KEY[:8]}…")
print("\nThis flow will generate access tokens for whichever account authorises the app.")
print("Make sure you are LOGGED IN TO THE BETEYE ACCOUNT before opening the URL.\n")

# Step 1 — get a request token
oauth1 = tweepy.OAuth1UserHandler(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    callback="oob",  # PIN-based flow — no redirect URL needed
)

try:
    auth_url = oauth1.get_authorization_url()
except tweepy.TweepyException as e:
    sys.exit(f"Failed to get authorization URL: {e}")

print(f"Authorization URL:\n{auth_url}\n")

open_browser = input("Open in browser automatically? [Y/n]: ").strip().lower()
if open_browser != "n":
    webbrowser.open(auth_url)

print("\n1. Log into the BETEYE account on X.")
print("2. Authorise the app.")
print("3. Copy the 6-7 digit PIN shown on screen.\n")

pin = input("Enter PIN: ").strip()
if not pin:
    sys.exit("No PIN entered — aborting.")

# Step 2 — exchange PIN for access tokens
try:
    access_token, access_token_secret = oauth1.get_access_token(pin)
except tweepy.TweepyException as e:
    sys.exit(f"Token exchange failed: {e}")

# Step 3 — verify which account these tokens belong to
try:
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    me = client.get_me()
    handle = f"@{me.data.username}" if me.data else "(unknown)"
except Exception:
    handle = "(could not verify)"

print(f"\n✓ Tokens generated for: {handle}")
print("\nAdd these to your .env file:\n")
print(f"X_ACCESS_TOKEN={access_token}")
print(f"X_ACCESS_TOKEN_SECRET={access_token_secret}")
print("\nThen restart the beteye-agent container:\n  docker compose restart beteye-agent\n")
