"""
BetEye image generation — contextual branded cards for every post type.

Brand palette (sampled from bet-eye-brand-logo-original-tr-bg.png):
  #00D4FF  electric cyan — ECG line, eye glow, accent numbers
  #0091CC  mid blue      — secondary accents, borders
  #003C78  deep navy     — glow base, inner rings
  #0A0E1A  near-black    — card background
  #FFFFFF  white         — headline text
  #A8B8CC  grey-blue     — body / subdued text

Three templates:
  match_card   — single fixture preview OR multi-fixture day card (matchday mode)
  stat_card    — big number + context lines (stat mode)
  branded_card — atmospheric BetEye branded background (take / news / list)
"""
import asyncio
import io
import logging
import math
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

log = logging.getLogger("beteye.image")

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
BG          = (10,  14,  26)     # #0A0E1A  card background
CYAN        = (0,  212, 255)     # #00D4FF  primary neon cyan
CYAN_MID    = (0,  145, 204)     # #0091CC  secondary blue
BLUE_DEEP   = (0,   60, 120)     # #003C78  deep blue
BLUE_DARK   = (5,   20,  55)     # #051437  darkest accent
WHITE       = (255, 255, 255)
GREY        = (168, 184, 204)    # #A8B8CC  body text
GREY_DIM    = (80,  95, 115)     # #505F73  subdued text

CARD_W, CARD_H = 1200, 675      # 16:9 — Twitter card standard

# Paths
LOGO_PATH = Path(__file__).parent.parent / "bet-eye-brand-logo-original-tr-bg.png"
TMP_DIR   = Path(os.environ.get("DATA_DIR", "/data")) / "img_tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Flag images via flagcdn.com — keyed by team name used in wc_schedule.json
TEAM_FLAGS: dict[str, str] = {
    "France":         "https://flagcdn.com/w320/fr.png",
    "Senegal":        "https://flagcdn.com/w320/sn.png",
    "Iraq":           "https://flagcdn.com/w320/iq.png",
    "Norway":         "https://flagcdn.com/w320/no.png",
    "Argentina":      "https://flagcdn.com/w320/ar.png",
    "Algeria":        "https://flagcdn.com/w320/dz.png",
    "Jordan":         "https://flagcdn.com/w320/jo.png",
    "Austria":        "https://flagcdn.com/w320/at.png",
    "Saudi Arabia":   "https://flagcdn.com/w320/sa.png",
    "Uruguay":        "https://flagcdn.com/w320/uy.png",
    "Brazil":         "https://flagcdn.com/w320/br.png",
    "England":        "https://flagcdn.com/w320/gb-eng.png",
    "Spain":          "https://flagcdn.com/w320/es.png",
    "Germany":        "https://flagcdn.com/w320/de.png",
    "Portugal":       "https://flagcdn.com/w320/pt.png",
    "Netherlands":    "https://flagcdn.com/w320/nl.png",
    "Belgium":        "https://flagcdn.com/w320/be.png",
    "Italy":          "https://flagcdn.com/w320/it.png",
    "Croatia":        "https://flagcdn.com/w320/hr.png",
    "Mexico":         "https://flagcdn.com/w320/mx.png",
    "USA":            "https://flagcdn.com/w320/us.png",
    "Colombia":       "https://flagcdn.com/w320/co.png",
    "Japan":          "https://flagcdn.com/w320/jp.png",
    "South Korea":    "https://flagcdn.com/w320/kr.png",
    "Morocco":        "https://flagcdn.com/w320/ma.png",
    "Ghana":          "https://flagcdn.com/w320/gh.png",
    "Cameroon":       "https://flagcdn.com/w320/cm.png",
    "Egypt":          "https://flagcdn.com/w320/eg.png",
    "Tunisia":        "https://flagcdn.com/w320/tn.png",
    "Mali":           "https://flagcdn.com/w320/ml.png",
    "Ivory Coast":    "https://flagcdn.com/w320/ci.png",
    "Nigeria":        "https://flagcdn.com/w320/ng.png",
    "Comoros":        "https://flagcdn.com/w320/km.png",
    "Cape Verde":     "https://flagcdn.com/w320/cv.png",
    "Australia":      "https://flagcdn.com/w320/au.png",
    "New Zealand":    "https://flagcdn.com/w320/nz.png",
    "Iran":           "https://flagcdn.com/w320/ir.png",
    "Qatar":          "https://flagcdn.com/w320/qa.png",
    "Canada":         "https://flagcdn.com/w320/ca.png",
    "Ecuador":        "https://flagcdn.com/w320/ec.png",
    "Bolivia":        "https://flagcdn.com/w320/bo.png",
    "Paraguay":       "https://flagcdn.com/w320/py.png",
    "Chile":          "https://flagcdn.com/w320/cl.png",
    "Venezuela":      "https://flagcdn.com/w320/ve.png",
    "Peru":           "https://flagcdn.com/w320/pe.png",
    "Panama":         "https://flagcdn.com/w320/pa.png",
    "Costa Rica":     "https://flagcdn.com/w320/cr.png",
    "Honduras":       "https://flagcdn.com/w320/hn.png",
    "Switzerland":    "https://flagcdn.com/w320/ch.png",
    "Denmark":        "https://flagcdn.com/w320/dk.png",
    "Sweden":         "https://flagcdn.com/w320/se.png",
    "Poland":         "https://flagcdn.com/w320/pl.png",
    "Serbia":         "https://flagcdn.com/w320/rs.png",
    "Ukraine":        "https://flagcdn.com/w320/ua.png",
    "Turkey":         "https://flagcdn.com/w320/tr.png",
    "Greece":         "https://flagcdn.com/w320/gr.png",
    "Scotland":       "https://flagcdn.com/w320/gb-sct.png",
    "Wales":          "https://flagcdn.com/w320/gb-wls.png",
    "Slovakia":       "https://flagcdn.com/w320/sk.png",
    "Romania":        "https://flagcdn.com/w320/ro.png",
    "Albania":        "https://flagcdn.com/w320/al.png",
    "Georgia":        "https://flagcdn.com/w320/ge.png",
    "Slovenia":       "https://flagcdn.com/w320/si.png",
    "Czech Republic": "https://flagcdn.com/w320/cz.png",
    "Hungary":        "https://flagcdn.com/w320/hu.png",
    "UAE":            "https://flagcdn.com/w320/ae.png",
    "Indonesia":      "https://flagcdn.com/w320/id.png",
    "Thailand":       "https://flagcdn.com/w320/th.png",
    "Vietnam":        "https://flagcdn.com/w320/vn.png",
    "Philippines":    "https://flagcdn.com/w320/ph.png",
    "India":          "https://flagcdn.com/w320/in.png",
    "China":          "https://flagcdn.com/w320/cn.png",
    "Uzbekistan":     "https://flagcdn.com/w320/uz.png",
    "South Africa":   "https://flagcdn.com/w320/za.png",
    "DR Congo":       "https://flagcdn.com/w320/cd.png",
    "Tanzania":       "https://flagcdn.com/w320/tz.png",
    "Zimbabwe":       "https://flagcdn.com/w320/zw.png",
    "Libya":          "https://flagcdn.com/w320/ly.png",
    "Lebanon":        "https://flagcdn.com/w320/lb.png",
    "Syria":          "https://flagcdn.com/w320/sy.png",
    "Bahrain":        "https://flagcdn.com/w320/bh.png",
    "Kuwait":         "https://flagcdn.com/w320/kw.png",
}

# ---------------------------------------------------------------------------
# Font loading — searches system paths installed in Dockerfile
# ---------------------------------------------------------------------------
_FONT_SEARCH = [
    Path(__file__).parent / "fonts",
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/freefont"),
    Path("/usr/share/fonts/truetype/open-sans"),
    Path("/usr/share/fonts"),
]


def _font(keywords: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Find best matching .ttf font; gracefully fall back to PIL default."""
    for d in _FONT_SEARCH:
        if not d.exists():
            continue
        for ttf in sorted(d.rglob("*.ttf")):
            lower = ttf.name.lower()
            if all(k.lower() in lower for k in keywords):
                try:
                    return ImageFont.truetype(str(ttf), size)
                except Exception:
                    pass
    # Try any bold font when specific match fails
    if "bold" in [k.lower() for k in keywords]:
        for d in _FONT_SEARCH:
            if not d.exists():
                continue
            for ttf in sorted(d.rglob("*.ttf")):
                if "bold" in ttf.name.lower():
                    try:
                        return ImageFont.truetype(str(ttf), size)
                    except Exception:
                        pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# Font set — loaded once at module import
F = {
    "hero":   _font(["bold"], 104),
    "big":    _font(["bold"], 70),
    "title":  _font(["bold"], 52),
    "sub":    _font(["bold"], 40),
    "body":   _font([""], 34),
    "small":  _font([""], 26),
    "label":  _font(["bold"], 22),
    "tiny":   _font([""], 19),
}


# ---------------------------------------------------------------------------
# Drawing utilities
# ---------------------------------------------------------------------------

def _new_card() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (CARD_W, CARD_H), BG + (255,))
    return img, ImageDraw.Draw(img)


def _glow(img: Image.Image, cx: int, cy: int, radius: int, color: tuple, alpha: float = 0.30) -> None:
    """Soft radial glow by blurring a colored ellipse onto the canvas."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r, g, b = color[:3]
    d.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(r, g, b, int(255 * alpha)),
    )
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius // 2)))


def _ecg(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int,
         color: tuple = CYAN, width: int = 3) -> None:
    """Draw the BetEye ECG / heartbeat signature line."""
    W = x1 - x0
    pts = [
        (x0,           y),
        (x0 + W * .28, y),
        (x0 + W * .31, y - 10),   # P bump
        (x0 + W * .34, y),
        (x0 + W * .40, y),
        (x0 + W * .43, y + 18),   # Q dip
        (x0 + W * .47, y - 82),   # R peak  ← tall spike
        (x0 + W * .51, y + 38),   # S dip
        (x0 + W * .55, y),
        (x0 + W * .62, y),
        (x0 + W * .65, y - 24),   # T wave
        (x0 + W * .68, y - 30),
        (x0 + W * .71, y - 24),
        (x0 + W * .74, y),
        (x1,           y),
    ]
    draw.line([(int(x), int(y2)) for x, y2 in pts], fill=color, width=width, joint="curve")


def _logo(img: Image.Image, w: int = 200, x: int | None = None,
          y: int | None = None, opacity: float = 1.0) -> None:
    """Paste the BetEye logo PNG onto the card."""
    if not LOGO_PATH.exists():
        return
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        h = int(w * logo.height / logo.width)
        logo = logo.resize((w, h), Image.LANCZOS)
        if opacity < 1.0:
            r, g, b, a = logo.split()
            a = a.point(lambda p: int(p * opacity))
            logo = Image.merge("RGBA", (r, g, b, a))
        px = x if x is not None else 40
        py = y if y is not None else CARD_H - h - 30
        img.alpha_composite(logo, (px, py))
    except Exception as e:
        log.debug(f"Logo paste error: {e}")


def _text_c(draw: ImageDraw.ImageDraw, text: str, y: int, font,
            fill: tuple, w: int = CARD_W) -> None:
    """Draw centered text."""
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text(((w - (bb[2] - bb[0])) // 2, y), text, font=font, fill=fill)


def _wrap_lines(text: str, font, max_w: int) -> list[str]:
    """Wrap text to fit within max_w pixels."""
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), test, font=font)
        if bb[2] > max_w and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


# ---------------------------------------------------------------------------
# Team logo fetching — async, disk-cached in TMP_DIR
# ---------------------------------------------------------------------------

async def _team_logo(url: str, size: int = 140) -> Image.Image | None:
    """Download a team crest and return a circular masked RGBA image."""
    if not url:
        return None
    cache = TMP_DIR / f"crest_{url.split('/')[-1]}"
    try:
        if cache.exists():
            raw = Image.open(cache).convert("RGBA")
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url)
                r.raise_for_status()
            raw = Image.open(io.BytesIO(r.content)).convert("RGBA")
            raw.save(cache)
        raw = raw.resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(raw, mask=mask)
        return out
    except Exception as e:
        log.debug(f"Crest fetch failed {url[:60]}: {e}")
        return None


def _initials_circle(name: str, size: int = 140) -> Image.Image:
    """Fallback circle with team initials when crest unavailable."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=BLUE_DEEP + (230,), outline=CYAN_MID, width=3)
    initials = "".join(w[0].upper() for w in name.split()[:2])
    fnt = _font(["bold"], size // 3)
    bb = d.textbbox((0, 0), initials, font=fnt)
    d.text(((size - (bb[2] - bb[0])) // 2, (size - (bb[3] - bb[1])) // 2),
           initials, font=fnt, fill=WHITE)
    return img


async def _team_logo_rect(url: str, w: int = 300, h: int = 200, radius: int = 14) -> Image.Image | None:
    """Download a flag/crest and return a rounded-rectangle RGBA image sized w×h."""
    if not url:
        return None
    cache = TMP_DIR / f"flag_{url.split('/')[-1]}"
    try:
        if cache.exists():
            raw = Image.open(cache).convert("RGBA")
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url)
                r.raise_for_status()
            raw = Image.open(io.BytesIO(r.content)).convert("RGBA")
            raw.save(cache)

        # Resize to fill target, cropping center to preserve aspect ratio
        src_ratio = raw.width / raw.height
        tgt_ratio = w / h
        if src_ratio > tgt_ratio:
            new_h = h
            new_w = int(raw.width * h / raw.height)
            raw = raw.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - w) // 2
            raw = raw.crop((left, 0, left + w, h))
        else:
            new_w = w
            new_h = int(raw.height * w / raw.width)
            raw = raw.resize((new_w, new_h), Image.LANCZOS)
            top = (new_h - h) // 2
            raw = raw.crop((0, top, w, top + h))

        # Apply rounded-corner mask
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        result.paste(raw.convert("RGBA"), mask=mask)
        return result
    except Exception as e:
        log.debug(f"Flag rect fetch failed {url[:60]}: {e}")
        return None


# ---------------------------------------------------------------------------
# Template 1 — MATCH CARD
# Handles 1 fixture (full detail) or 2–5 fixtures (compact multi-game list)
# ---------------------------------------------------------------------------

async def match_card(fixtures: list[dict]) -> Path:
    if len(fixtures) == 1:
        return await _single_match(fixtures[0])
    return await _multi_match(fixtures)


async def _single_match(fx: dict) -> Path:
    """Full-width single fixture preview with country flags."""
    img, draw = _new_card()

    home_name = fx.get("home", "Home")
    away_name = fx.get("away", "Away")

    # Background — split glow pulls the eye to each side then centre
    _glow(img, 250,          330, 420, CYAN_MID, 0.11)
    _glow(img, CARD_W - 250, 330, 420, CYAN_MID, 0.11)
    _glow(img, CARD_W // 2,  330, 200, CYAN,     0.08)

    # Top band
    draw.rectangle((0, 0, CARD_W, 70), fill=BLUE_DARK + (255,))
    label = (f"FIFA WORLD CUP 2026  ·  GROUP {fx.get('group', '?')}"
             f"  ·  MATCHDAY {fx.get('matchday', '?')}")
    _text_c(draw, label, 22, F["label"], (*CYAN_MID, 220))
    draw.line([(0, 70), (CARD_W, 70)], fill=(*CYAN, 160), width=2)

    # Fetch flags (prefer TEAM_FLAGS lookup; fall back to any API logo)
    flag_w, flag_h = 300, 200
    home_url = TEAM_FLAGS.get(home_name) or fx.get("home_logo", "")
    away_url = TEAM_FLAGS.get(away_name) or fx.get("away_logo", "")
    home_flag, away_flag = await asyncio.gather(
        _team_logo_rect(home_url, flag_w, flag_h),
        _team_logo_rect(away_url, flag_w, flag_h),
    )

    flag_cy   = 300
    flag_y    = flag_cy - flag_h // 2          # top of flag images
    home_cx   = 235                            # flag centre-x, home side
    away_cx   = CARD_W - 235                   # flag centre-x, away side
    home_fx   = home_cx - flag_w // 2
    away_fx   = away_cx - flag_w // 2

    # Subtle neon border glow behind each flag
    for cx in (home_cx, away_cx):
        _glow(img, cx, flag_cy, 170, CYAN, 0.14)
        draw.rounded_rectangle(
            (cx - flag_w // 2 - 4, flag_y - 4,
             cx + flag_w // 2 + 4, flag_y + flag_h + 4),
            radius=16, outline=(*CYAN_MID, 100), width=2,
        )

    # Paste flags (or initials fallback in the old circular style)
    for cx, name, flag_img, x in (
        (home_cx, home_name, home_flag, home_fx),
        (away_cx, away_name, away_flag, away_fx),
    ):
        if flag_img:
            img.alpha_composite(flag_img, (x, flag_y))
        else:
            fb = _initials_circle(name, flag_h)
            img.alpha_composite(fb, (cx - flag_h // 2, flag_y))

        draw.text((cx, flag_y + flag_h + 16), name.upper(),
                  font=F["sub"], fill=WHITE, anchor="mt")

    # VS — centred, neon
    _glow(img, CARD_W // 2, flag_cy, 110, CYAN, 0.30)
    draw.text((CARD_W // 2, flag_cy - 58), "VS",
              font=F["hero"], fill=CYAN, anchor="mt")

    # ECG signature
    ecg_y = 465
    _ecg(draw, 60, CARD_W - 60, ecg_y, (*CYAN, 210), width=3)

    # Kickoff / venue row
    kickoff = fx.get("kickoff_et", "TBD")
    city    = fx.get("city", "")
    venue   = fx.get("venue", "")
    info    = f"TODAY  ·  {kickoff} ET"
    if city:
        info += f"  ·  {city}"
    _text_c(draw, info,  488, F["body"],  GREY)
    if venue:
        _text_c(draw, venue, 530, F["small"], GREY_DIM)

    # Bottom bar
    draw.rectangle((0, 600, CARD_W, CARD_H), fill=BLUE_DARK + (255,))
    draw.line([(0, 600), (CARD_W, 600)], fill=(*CYAN, 180), width=2)
    _logo(img, w=190, x=40, y=610)
    draw.text((CARD_W - 50, 630), "@beteye_  ·  #WC2026",
              font=F["small"], fill=GREY_DIM, anchor="rt")

    slug = f"{fx.get('home','?')}_{fx.get('away','?')}_{fx.get('date','')}".replace(" ", "_")
    out  = TMP_DIR / f"match_{slug}.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


async def _multi_match(fixtures: list[dict]) -> Path:
    """Compact multi-fixture card — shows up to 5 games in a list."""
    img, draw = _new_card()

    # Background
    _glow(img, CARD_W // 2, 100, 400, CYAN_MID, 0.10)
    _glow(img, 100, CARD_H - 100, 300, BLUE_DEEP, 0.18)

    # Top band
    draw.rectangle((0, 0, CARD_W, 72), fill=BLUE_DARK + (255,))
    _text_c(draw, "FIFA WORLD CUP 2026  ·  TODAY'S FIXTURES", 22, F["label"], (*CYAN, 230))
    draw.line([(0, 72), (CARD_W, 72)], fill=(*CYAN, 150), width=2)

    # Fixture rows
    fx_to_show = fixtures[:5]
    row_h = (540 - 72) // max(len(fx_to_show), 1)
    pad_x = 70

    for i, fx in enumerate(fx_to_show):
        row_y = 82 + i * row_h
        mid_y = row_y + row_h // 2

        # Alternating row tint
        if i % 2 == 0:
            draw.rectangle((0, row_y, CARD_W, row_y + row_h - 2),
                           fill=(0, 30, 70, 40))

        # Home team
        home = fx.get("home", "")
        draw.text((pad_x, mid_y - 20), home.upper(), font=F["sub"], fill=WHITE, anchor="lm")

        # VS divider (centered)
        cx = CARD_W // 2
        draw.text((cx, mid_y - 10), "vs", font=F["body"], fill=(*CYAN, 180), anchor="mm")

        # Away team (right-aligned)
        away = fx.get("away", "")
        draw.text((CARD_W - pad_x, mid_y - 20), away.upper(),
                  font=F["sub"], fill=WHITE, anchor="rm")

        # Kickoff + group info (below team names)
        kickoff = fx.get("kickoff_et", "")
        group   = fx.get("group", "?")
        md      = fx.get("matchday", "?")
        meta    = f"{kickoff} ET  ·  Group {group}  ·  MD{md}"
        draw.text((cx, mid_y + 20), meta, font=F["tiny"], fill=GREY_DIM, anchor="mm")

        # Row separator
        if i < len(fx_to_show) - 1:
            draw.line([(pad_x, row_y + row_h - 2), (CARD_W - pad_x, row_y + row_h - 2)],
                      fill=(*CYAN_MID, 40), width=1)

    # ECG line
    ecg_y = 565
    _ecg(draw, 60, CARD_W - 60, ecg_y, (*CYAN, 200), width=3)

    # Bottom bar
    draw.rectangle((0, 600, CARD_W, CARD_H), fill=BLUE_DARK + (255,))
    draw.line([(0, 600), (CARD_W, 600)], fill=(*CYAN, 180), width=2)
    _logo(img, w=180, x=40, y=610)
    draw.text((CARD_W - 50, 630), "@beteye_  ·  #WC2026",
              font=F["small"], fill=GREY_DIM, anchor="rt")

    out = TMP_DIR / f"multi_match_{int(datetime.now(timezone.utc).timestamp())}.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


# ---------------------------------------------------------------------------
# Template 2 — STAT CARD
# Big headline number + 1–3 context lines
# ---------------------------------------------------------------------------

def stat_card(headline: str, context: list[str], label: str = "WC 2026 STAT") -> Path:
    img, draw = _new_card()

    # Asymmetric glow — top-left data/intel feel
    _glow(img, 160, 160, 380, CYAN, 0.14)
    _glow(img, CARD_W - 80, CARD_H - 80, 300, BLUE_DEEP, 0.22)

    # Left cyan accent bar
    draw.rectangle((0, 0, 7, CARD_H), fill=(*CYAN, 255))

    # Label
    draw.text((80, 52), label.upper(), font=F["label"], fill=(*CYAN, 220))

    # Headline — up to 2 lines, first line in cyan, second in white
    lines = _wrap_lines(headline, F["hero"], CARD_W - 160)
    y = 115
    for i, line in enumerate(lines[:2]):
        fnt   = F["hero"] if i == 0 else F["big"]
        color = CYAN      if i == 0 else WHITE
        draw.text((80, y), line, font=fnt, fill=color)
        bb = draw.textbbox((80, y), line, font=fnt)
        y  = bb[3] + 14

    # Context lines
    y = max(y + 24, 370)
    for line in context[:3]:
        wrapped = _wrap_lines(line, F["body"], CARD_W - 160)
        for wl in wrapped[:2]:
            draw.text((80, y), wl, font=F["body"], fill=GREY)
            bb = draw.textbbox((80, y), wl, font=F["body"])
            y  = bb[3] + 10
        y += 8

    # ECG line divider
    ecg_y = 568
    _ecg(draw, 60, CARD_W - 60, ecg_y, (*CYAN, 200), width=3)

    # Bottom
    _logo(img, w=170, x=40, y=592)
    draw.text((CARD_W - 50, 620), "@beteye_  ·  #WC2026",
              font=F["small"], fill=GREY_DIM, anchor="rt")

    out = TMP_DIR / f"stat_{int(datetime.now(timezone.utc).timestamp())}.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


# ---------------------------------------------------------------------------
# Template 3 — BRANDED CARD
# Atmospheric BetEye background — take / narrative / news posts
# ---------------------------------------------------------------------------

def branded_card(mood: str = "default") -> Path:
    """
    mood: 'default' | 'intense' (breaking / big moment) | 'calm' (analysis / intel)
    """
    img, draw = _new_card()

    if mood == "intense":
        _glow(img, CARD_W // 2, CARD_H // 2, 550, CYAN, 0.20)
        _glow(img, CARD_W // 2, CARD_H // 2, 260, CYAN, 0.12)
        _glow(img, CARD_W // 2, CARD_H // 2, 100, WHITE, 0.04)
    elif mood == "calm":
        _glow(img, 120, CARD_H // 2, 420, CYAN_MID, 0.13)
        _glow(img, CARD_W - 120, CARD_H // 2, 380, BLUE_DEEP, 0.20)
    else:
        _glow(img, CARD_W // 2, 160, 450, CYAN_MID, 0.15)
        _glow(img, CARD_W // 2, CARD_H, 380, BLUE_DEEP, 0.22)

    # Subtle grid overlay — data/tech feel
    grid_c = (0, 80, 140, 22)
    for x in range(0, CARD_W, 80):
        draw.line([(x, 0), (x, CARD_H)], fill=grid_c, width=1)
    for y in range(0, CARD_H, 80):
        draw.line([(0, y), (CARD_W, y)], fill=grid_c, width=1)

    # Top + bottom cyan bars
    draw.rectangle((0, 0, CARD_W, 5), fill=(*CYAN, 255))
    draw.rectangle((0, CARD_H - 5, CARD_W, CARD_H), fill=(*CYAN, 255))

    # ECG line at ~58% height
    ecg_y = int(CARD_H * 0.60)
    _ecg(draw, 60, CARD_W - 60, ecg_y, (*CYAN, 185), width=4)

    # Central logo — large and prominent
    logo_w = 440
    _logo(img, w=logo_w, x=(CARD_W - logo_w) // 2, y=150, opacity=0.97)

    # Tagline
    _text_c(draw, "BETTING INTELLIGENCE  ·  WC 2026",
            CARD_H - 52, F["label"], (*GREY_DIM, 200))

    out = TMP_DIR / f"brand_{mood}_{int(datetime.now(timezone.utc).timestamp())}.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


# ---------------------------------------------------------------------------
# Public API — called from agent.py post_job
# ---------------------------------------------------------------------------

async def generate_post_image(
    item: dict,
    mode: str,
    post_text: str,
    today_fixtures: list[dict] | None = None,
) -> Path | None:
    """
    Generate the most contextually relevant image for a post.
    Returns path to a PNG in TMP_DIR, or None on failure.

    For scheduled matchday/stat posts, item["_fixture"] holds the specific fixture
    so we generate a single-match card rather than a multi-game list.
    """
    try:
        if mode == "matchday":
            # Prefer the specific fixture attached to this scheduled post
            fx = item.get("_fixture")
            if fx:
                return await match_card([fx])          # single-match card
            if today_fixtures:
                return await match_card(today_fixtures[:1])  # fallback: first of today
            return branded_card()

        if mode == "stat":
            # Show the fixture card + stat overlay
            fx = item.get("_fixture")
            if fx:
                return await match_card([fx])
            lines    = [l.strip() for l in post_text.split("\n") if l.strip()]
            headline = lines[0] if lines else item.get("title", "")[:80]
            context  = lines[1:4]
            return stat_card(headline, context)

        if mode == "news":
            mood = "intense" if item.get("is_breaking") else "calm"
            # If the news concerns a team playing today, show their match card
            if today_fixtures and _news_about_today(item, today_fixtures):
                relevant = [f for f in today_fixtures
                            if _news_about_today(item, [f])]
                return await match_card(relevant[:1])
            return branded_card(mood=mood)

        if mode == "take":
            return branded_card(mood="calm")

        if mode == "list":
            return branded_card(mood="default")

        return branded_card(mood="default")

    except Exception as e:
        log.warning(f"[image] Generation failed ({mode}): {e}")
        return None


def _news_about_today(item: dict, fixtures: list[dict]) -> bool:
    """Check if a news item is about a team playing today."""
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    for fx in fixtures:
        if fx.get("home", "").lower() in text or fx.get("away", "").lower() in text:
            return True
    return False
