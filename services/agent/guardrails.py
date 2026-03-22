"""
Guardrails: safety rules applied before any transaction executes.
"""

import re

MAX_AMOUNT = 1000

# Known valid destinations (names or currency codes)
ALLOWED_DESTINATIONS = {
    "ghana", "nigeria", "kenya", "uk", "usa", "europe",
    "ghs", "ngn", "kes", "gbp", "usd", "eur",
    "savings", "wallet", "family", "friend",
}

# Phrases that signal prompt injection or unsafe instructions
BLOCKED_PHRASES = [
    "ignore previous",
    "ignore all",
    "send everything",
    "transfer all",
    "override",
    "jailbreak",
    "forget rules",
    "disregard",
]

# Looks like a random crypto wallet address (hex string > 20 chars)
WALLET_ADDRESS_PATTERN = re.compile(r'\b[a-fA-F0-9]{20,}\b')


def check(intent: dict, raw_input: str) -> tuple[bool, str]:
    """
    Returns (is_safe: bool, reason: str).
    Call this before execution.
    """
    raw_lower = raw_input.lower()

    # 1. Block prompt injection / adversarial phrases
    for phrase in BLOCKED_PHRASES:
        if phrase in raw_lower:
            return False, f"Blocked: instruction contains disallowed phrase '{phrase}'."

    # 2. Block random wallet/address strings
    if WALLET_ADDRESS_PATTERN.search(raw_input):
        return False, "Blocked: destination looks like an unverified wallet address."

    # 3. Amount cap
    amount = intent.get("amount", 0)
    if amount is None:
        return False, "Blocked: could not determine transaction amount."
    if amount > MAX_AMOUNT:
        return False, f"Blocked: amount £{amount} exceeds the £{MAX_AMOUNT} limit."
    if amount <= 0:
        return False, "Blocked: amount must be greater than £0."

    # 4. Unknown destination
    destination = (intent.get("destination") or "").lower().strip()
    if destination and destination not in ALLOWED_DESTINATIONS:
        return False, f"Blocked: destination '{destination}' is not recognised. Allowed: {', '.join(sorted(ALLOWED_DESTINATIONS))}."

    return True, "OK"
