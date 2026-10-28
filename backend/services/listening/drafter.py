"""Turn an eligible post into a reply draft from an approved template.

Slot filling is plain code, not AI: approved copy reaches X exactly as approved,
with only the facts (match, minute, alert, proof link, signup link) dropped in.
"""
import re
import secrets
import string

from services.listening.filters import banned_claims, has_responsible_footer

SLOTS = {"match", "alert_type", "minute", "outcome", "proof_url", "link"}
PROOF_SLOTS = {"match", "alert_type", "minute", "outcome", "proof_url"}
INTENTS = {"any", "seeking_live_alerts", "seeking_tips", "tipster_complaint", "odds_discussion"}
_SLOT_RE = re.compile(r"\{([a-z_]+)\}")
_CODE_ALPHABET = string.ascii_letters + string.digits


def template_slots(body: str) -> set[str]:
    return set(_SLOT_RE.findall(body))


def validate_template(body: str, intent: str) -> list[str]:
    """Problems that stop a template being saved."""
    errors = []
    unknown = template_slots(body) - SLOTS
    if unknown:
        errors.append(f"Unknown slots: {', '.join(sorted(unknown))}. Allowed: {', '.join(sorted(SLOTS))}")
    if "link" not in template_slots(body):
        errors.append("Template must include {link} so signups can be traced")
    if not has_responsible_footer(body):
        errors.append('Template must include "18+" and "Play responsibly"')
    claims = banned_claims(body)
    if claims:
        errors.append(f"Banned claims: {', '.join(claims)}")
    if intent not in INTENTS:
        errors.append(f"Intent must be one of: {', '.join(sorted(INTENTS))}")
    return errors


def is_usable(template) -> bool:
    return bool(template.active and template.approved_at and template.arcon_cert_no)


def pick_template(templates: list, intent: str, have_proof: bool):
    """An approved template for this intent (specific before 'any'); proof templates need proof."""
    usable = [
        t for t in templates
        if is_usable(t) and t.intent in (intent, "any")
        and (have_proof or not (template_slots(t.body) & PROOF_SLOTS))
    ]
    def rank(t):
        uses_proof = bool(template_slots(t.body) & PROOF_SLOTS)
        # intent-specific first, then templates that show proof, then oldest
        return (t.intent != intent, not uses_proof, t.id)

    usable.sort(key=rank)
    return usable[0] if usable else None


def new_code() -> str:
    return "vx_" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))


def build_link(link_base: str, code: str) -> str:
    sep = "&" if "?" in link_base else "?"
    return f"{link_base}{sep}startapp={code}"


def _humanise(alert_type: str) -> str:
    return alert_type.replace("_", " ").lower()


def render(template_body: str, proof: dict | None, link: str) -> str:
    values = {"link": link}
    if proof:
        values.update({
            "match": proof.get("match", ""),
            "alert_type": _humanise(str(proof.get("alertType", ""))),
            "minute": str(proof.get("minuteAtFire", "")),
            "outcome": "won" if proof.get("outcome") == "WIN" else str(proof.get("outcome", "")).lower(),
            "proof_url": proof.get("proofUrl") or "",
        })
    return _SLOT_RE.sub(lambda m: values.get(m.group(1), ""), template_body).strip()


def check_draft(text: str) -> list[str]:
    """Re-run on every draft and every reviewer edit."""
    errors = []
    if not has_responsible_footer(text):
        errors.append('Draft must keep "18+" and "Play responsibly"')
    claims = banned_claims(text)
    if claims:
        errors.append(f"Banned claims: {', '.join(claims)}")
    return errors
