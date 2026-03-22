"""
Agent: parses user intent via Claude API and orchestrates the flow.
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
                "Run: export ANTHROPIC_API_KEY=your_key"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a financial intent parser. Extract structured data from the user's instruction.

Return ONLY valid JSON with these fields:
{
  "action": "send" | "split" | "save" | "unknown",
  "amount": <number or null>,
  "destination": "<string or null>",
  "split": [{"destination": "<string>", "amount": <number>}] or null,
  "reasoning": "<one sentence explaining what the user wants>"
}

Rules:
- amount must be a number (no currency symbols)
- destination should be a plain name (e.g. "ghana", "savings", "wallet")
- For split instructions, populate the split array with each leg
- If something is ambiguous, set it to null and explain in reasoning
"""


def parse_intent(user_input: str) -> dict:
    """Send user input to Claude and get structured intent back."""
    client = _get_client()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_input}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "action": "unknown",
            "amount": None,
            "destination": None,
            "split": None,
            "reasoning": f"Could not parse response: {raw[:120]}",
        }
