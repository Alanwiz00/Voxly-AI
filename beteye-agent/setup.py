"""
Idempotent setup — safe to run multiple times.
Creates the Beteye World Cup persona and topics only if they don't already exist.

Usage:
    python setup.py            # create missing, reuse existing
    python setup.py --purge    # delete ALL duplicate Beteye personas/topics first, then recreate
"""
import sys
import time
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("VOXLY_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("VOXLY_API_KEY") or os.environ.get("BETEYE_API_KEY", "")

if not API_KEY:
    print("ERROR: Set VOXLY_API_KEY in beteye-agent/.env  OR  BETEYE_API_KEY in the root .env")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
PURGE = "--purge" in sys.argv

# ---------------------------------------------------------------------------
# Persona definition
# ---------------------------------------------------------------------------
PERSONA_NAME = "Beteye — World Cup Insider"
PERSONA = {
    "name": PERSONA_NAME,
    "niche": "FIFA World Cup 2026, international football, global football tournaments, player transfers affecting national squads",
    "target_audience": "Football fans aged 18-45 globally, World Cup enthusiasts, sports bettors, fantasy football players, casual fans who want to stay updated",
    "tone": "Rapid-fire, passionate, football-native. Punchy and direct. Confident hot takes. Never fluffy or corporate. Creates FOMO. Makes readers feel they're missing out if they scroll past.",
    "brand_voice": (
        "The voice of a fan who lives and breathes football — deeply informed but never pretentious. "
        "Leads with the most shocking or surprising fact. Uses numbers and stats naturally. "
        "Drops names like a real fan. Ends with a question or a take that sparks debate. "
        "Feels like a text from your football-obsessed friend, not a press release."
    ),
    "writing_style_notes": (
        "- Short punchy sentences. One idea per sentence. No padding.\n"
        "- Lead with the hook — the most surprising or provocative fact first.\n"
        "- Use real numbers: '73 minutes', '3 clean sheets', '$180M release clause'.\n"
        "- Name players and clubs directly. Never say 'the player' or 'the club'.\n"
        "- No emojis. No hashtags unless they are genuinely the only way to say it.\n"
        "- End with a question or a hot take that demands a reply.\n"
        "- Max 250 characters. Every word must earn its place or it gets cut.\n"
        "- Do NOT start with 'I'.\n"
        "- NEVER state a time ('today', 'yesterday', 'this morning', 'earlier') unless "
        "the source explicitly confirms it. If the timing is unclear, state the fact without "
        "a timeline — fabricated timelines destroy credibility.\n"
        "- BANNED phrases — using any of these is an automatic failure: "
        "game-changer, game changer, double high-five, let that sink in, buckle up, "
        "this is huge, groundbreaking, revolutionary, it's no secret, dive into, delve into, "
        "in a world where, at the end of the day, moving the needle, it's worth noting, "
        "make no mistake, what a time to be alive, truly remarkable, I cannot stress enough, "
        "think about that for a second, rest assured, needless to say, without further ado, "
        "it's important to note, the beautiful game (as cliché), football is more than a sport.\n"
        "- Write like a football fan texting a mate who follows the game obsessively — "
        "not a journalist, not a PR account, not an AI assistant."
    ),
    "sample_content": (
        "Morocco's press just broke Spain. 14 ball recoveries in 90 minutes. "
        "Nobody is talking about how physical this squad is. Genuine dark horse.\n\n"
        "The last 5 World Cup winners all had a dominant #6. "
        "England don't have one. That's the conversation nobody wants to have.\n\n"
        "Mbappe doesn't need the ball at his feet. His movement off the ball pulls defenses apart. "
        "Teams know this. They still can't stop it. That's elite.\n\n"
        "Brazil have 6 players who start for top-5 European clubs. "
        "Argentina have 4. Depth wins tournaments. Who's got the deepest bench in 2026?\n\n"
        "Germany conceded 0 goals in their last 4 qualifiers. "
        "Nobody is talking about this. They're coming."
    ),
}

# ---------------------------------------------------------------------------
# Topic definitions — name is the deduplication key
# ---------------------------------------------------------------------------
TOPICS = [
    {
        "name": "FIFA World Cup 2026",
        "keywords": "World Cup 2026, FIFA, tournament, group stage, knockout, Metlife, SoFi, Azteca, host city",
        "description": "Main tournament coverage — results, fixtures, group standings, bracket updates",
    },
    {
        "name": "World Cup 2026 Squad & Team News",
        "keywords": "World Cup squad, national team selection, injury, call-up, lineup, starting XI, suspension, fitness",
        "description": "Player availability, squad announcements, injury updates for all national teams",
    },
    {
        "name": "World Cup 2026 Match Analysis",
        "keywords": "World Cup match, tactics, formation, pressing, xG, highlight, goal, red card, penalty, VAR, upset",
        "description": "Post-match breakdowns, tactical analysis, key moments and stats",
    },
    {
        "name": "World Cup 2026 Transfers & Rumors",
        "keywords": "transfer, signing, contract, fee, here we go, bid, loan, release clause, Fabrizio, done deal",
        "description": "Transfer activity affecting World Cup squads and player availability",
    },
    {
        "name": "World Cup 2026 Predictions & Odds",
        "keywords": "World Cup prediction, favourite, dark horse, odds, betting, winner, golden boot, top scorer, analyst",
        "description": "Pre-tournament and ongoing predictions, odds movements, expert picks",
    },
]
TOPIC_NAMES = {t["name"] for t in TOPICS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _delete(client: httpx.Client, path: str, item: dict, label: str):
    r = client.delete(f"{path}/{item['id']}")
    ok = r.status_code in (200, 204)
    print(f"   {'✓' if ok else '✗'} Deleted {label} id={item['id']} '{item.get('name', '')}'")


def run():
    with httpx.Client(base_url=API_URL, headers=HEADERS, timeout=120.0) as client:

        # ---- Fetch current state -------------------------------------------
        existing_personas = client.get("/persona/").json() or []
        existing_topics   = client.get("/topics/").json() or []

        beteye_personas = [p for p in existing_personas if PERSONA_NAME in (p.get("name") or "")]
        beteye_topics   = [t for t in existing_topics if t.get("name") in TOPIC_NAMES]

        # ---- Purge mode: wipe everything and start clean -------------------
        if PURGE:
            print("\n🗑  Purging all Beteye personas and topics...")
            for p in beteye_personas:
                _delete(client, "/persona", p, "persona")
            for t in beteye_topics:
                _delete(client, "/topics", t, "topic")
            beteye_personas = []
            beteye_topics   = []
            print("   Done.\n")

        # ---- Persona -------------------------------------------------------
        print("\n🏆 Persona:")
        if beteye_personas:
            for dupe in beteye_personas[1:]:
                print(f"   ⚠  Removing duplicate  id={dupe['id']}")
                _delete(client, "/persona", dupe, "persona")
            persona_id = beteye_personas[0]["id"]
            print(f"   ✓ Already exists  id={persona_id}  '{PERSONA_NAME}'")
        else:
            resp = client.post("/persona/", json=PERSONA)
            if resp.status_code in (200, 201):
                persona_id = resp.json()["id"]
                print(f"   ✓ Created  id={persona_id}  '{PERSONA_NAME}'")
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                print(f"   ✗ Failed {resp.status_code}: {detail}")
                print("   Hint: docker compose exec backend touch /app/main.py  (force reload)")
                print("   Then: docker compose logs backend --tail=60 | grep -i 'embed\\|error'")
                persona_id = None
            time.sleep(2)

        # ---- Topics --------------------------------------------------------
        print("\n📌 Topics:")
        existing_by_name = {t["name"]: t for t in beteye_topics}
        topic_ids = []

        for topic in TOPICS:
            name = topic["name"]
            if name in existing_by_name:
                tid = existing_by_name[name]["id"]
                topic_ids.append(tid)
                print(f"   ✓ Already exists  id={tid}  '{name}'")
            else:
                resp = client.post("/topics/", json=topic)
                if resp.status_code in (200, 201):
                    tid = resp.json()["id"]
                    topic_ids.append(tid)
                    print(f"   ✓ Created  id={tid}  '{name}'")
                else:
                    print(f"   ✗ Failed '{name}': {resp.status_code} — {resp.text}")
                time.sleep(2)

        # ---- Summary -------------------------------------------------------
        print("\n" + "=" * 60)
        print("Add to your root .env:")
        print("=" * 60)
        if persona_id:
            print(f"BETEYE_PERSONA_ID={persona_id}")
        print(f"# topic IDs: {topic_ids}")
        print("=" * 60)
        if not persona_id:
            sys.exit(1)


if __name__ == "__main__":
    run()
