"""
Policy inspection: the mandatory control layer before any execution.

No value moves unless this layer explicitly approves the proposed action.
This is not optional and cannot be bypassed by the agent or the user.

Inspection checks (in order):
  1. Blocked phrases   — adversarial instructions, prompt injection attempts
  2. Suspicious addresses — raw wallet strings that were not resolved by the
                            system (indicates an attempt to target an
                            unverified external address directly)
  3. Amount policy     — hard cap of £1,000 per coordinated action
  4. Destination policy— only known, allowlisted destinations are permitted

If any check fails, a structured report is returned with approved=False
and a clear reason. The execution layer gates on this verdict.
"""

import re

MAX_AMOUNT = 1000

# Add new verified destinations here before the demo
ALLOWED_DESTINATIONS = {
    "ghana", "nigeria", "kenya", "uk", "usa", "europe",
    "ghs", "ngn", "kes", "gbp", "usd", "eur",
    "savings", "wallet", "ledger", "family", "friend", "transfer",
}

# Phrases that indicate adversarial intent or prompt injection
BLOCKED_PHRASES = [
    "ignore previous",
    "ignore all",
    "ignore instructions",
    "send everything",
    "transfer all",
    "override",
    "jailbreak",
    "forget rules",
    "disregard",
    "bypass",
    "skip rules",
    "no guardrails",
]

# Raw wallet strings the user typed directly — not resolved by the system
# Catches: 0x-prefixed strings and long hex blobs
RAW_WALLET_PATTERN = re.compile(
    r'0x[a-zA-Z0-9]{4,}'
    r'|\b[a-fA-F0-9]{20,}\b',
    re.IGNORECASE,
)


def inspect(intent: dict, raw_input: str) -> dict:
    """
    Run all policy checks against the proposed action.

    Returns:
    {
        "approved": bool,
        "reason":   str,
        "checks":   [{"rule": str, "passed": bool, "detail": str | None}]
    }

    The caller MUST verify approved == True before invoking execution.
    """
    raw_lower = raw_input.lower()
    checks    = []

    # ── Check 1: Adversarial / injected phrases ───────────────────────────────
    hit = next((p for p in BLOCKED_PHRASES if p in raw_lower), None)
    checks.append({
        "rule":   "No adversarial phrases",
        "passed": hit is None,
        "detail": f'"{hit}"' if hit else None,
    })

    # ── Check 2: Raw unresolved wallet address ────────────────────────────────
    match = RAW_WALLET_PATTERN.search(raw_input)
    checks.append({
        "rule":   "No raw wallet addresses",
        "passed": match is None,
        "detail": match.group() if match else None,
    })

    # ── Check 3: Amount policy ────────────────────────────────────────────────
    amount = intent.get("amount")
    if amount is None:
        checks.append({"rule": "Amount resolvable", "passed": False, "detail": "could not determine amount"})
    elif amount <= 0:
        checks.append({"rule": "Amount > £0",       "passed": False, "detail": f"£{amount}"})
    else:
        within = amount <= MAX_AMOUNT
        checks.append({
            "rule":   f"Amount within £{MAX_AMOUNT:,} policy limit",
            "passed": within,
            "detail": f"£{amount:.2f} exceeds limit" if not within else f"£{amount:.2f}",
        })

    # ── Check 4: Destination policy ───────────────────────────────────────────
    destination = (intent.get("destination") or "").lower().strip()
    if destination:
        known = destination in ALLOWED_DESTINATIONS
        checks.append({
            "rule":   "Destination on allowlist",
            "passed": known,
            "detail": f'"{destination}" — not recognised' if not known else destination,
        })
    else:
        checks.append({
            "rule":   "Destination on allowlist",
            "passed": True,
            "detail": "n/a (split — checked per leg)",
        })

    # ── Verdict ───────────────────────────────────────────────────────────────
    failed = next((c for c in checks if not c["passed"]), None)
    if failed:
        detail = f": {failed['detail']}" if failed.get("detail") else ""
        return {
            "approved": False,
            "reason":   f"{failed['rule']}{detail}",
            "checks":   checks,
        }

    return {"approved": True, "reason": "All policy checks passed", "checks": checks}


def is_destination_allowed(destination: str) -> bool:
    """Quick check for per-leg destination validation during execution."""
    return (destination or "").lower().strip() in ALLOWED_DESTINATIONS
