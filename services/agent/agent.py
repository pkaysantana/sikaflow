"""
Intent resolution: translates a high-level user instruction into a
structured action the coordination system can act on.

The user expresses what they want to happen with their money.
This layer extracts the intent — amount, destination, action type —
without asking the user to specify rails, fees, or execution steps.
The system decides those.
"""

import os
import json
import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it before running: export ANTHROPIC_API_KEY=sk-..."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are the intent resolution layer of an autonomous financial coordination system.

The user expresses high-level financial intent. Your job is to extract the structured action.
The system will decide routing, rails, and execution automatically — you only resolve intent.

Return ONLY valid JSON with these fields:
{
  "action": "send" | "split" | "save" | "unknown",
  "amount": <number or null>,
  "destination": "<plain string or null — e.g. ghana, savings, family, nigeria>",
  "split": [{"destination": "<string>", "amount": <number>}] or null,
  "reasoning": "<one sentence: what value movement is being requested>"
}

Rules:
- amount is always a plain number (strip currency symbols)
- destination is a plain label: country name, "savings", "wallet", "family", etc.
- For split instructions, populate split with each leg; infer equal amounts if not stated
- If intent is ambiguous or unsafe, set action to "unknown" and explain in reasoning
- reasoning should describe the coordination intent clearly and concisely
"""


def parse_intent(user_input: str) -> dict:
    """
    Resolve a natural-language instruction into a structured intent.
    Returns a dict with action, amount, destination, split, reasoning.
    """
    client = _get_client()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_input}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if the model wraps its response
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "action":      "unknown",
            "amount":      None,
            "destination": None,
            "split":       None,
            "reasoning":   f"Could not parse model response: {raw[:120]}",
        }
