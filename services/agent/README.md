# Sikaflow – Autonomous Financial Coordination Agent

> "Sika" means money in Twi (Ghana). This CLI agent interprets natural-language financial instructions and simulates optimal cross-border transfers.

## What it does

1. **Parses** your plain-English instruction using Claude AI
2. **Checks** safety guardrails (amount caps, blocked phrases, unknown destinations)
3. **Selects** the cheapest available route (bank transfer vs stablecoin)
4. **Simulates** execution with fee breakdown and savings comparison

## Setup

```bash
cd services/agent
python main.py
```

## Example commands

```
> Send £50 to Ghana
> Transfer £200 to Nigeria
> Send £30 to Kenya
> Split £100 between savings and family
```

## Guardrails in action

```
> Send £2000 to Ghana           →  Blocked: exceeds £1000 limit
> Send £50 to 0xdeadbeef...     →  Blocked: unverified wallet address
> Ignore previous rules         →  Blocked: disallowed phrase
```

## File structure

```
services/agent/
├── main.py        ← CLI loop & output formatting
├── agent.py       ← Claude API call & intent parsing
├── routes.py      ← Route definitions & fee calculation
└── guardrails.py  ← Safety rules
```

## Quick tweaks for the demo

| What to change | Where |
|---|---|
| Add a destination | `guardrails.py` → `ALLOWED_DESTINATIONS` |
| Add a route | `routes.py` → `ROUTES` list |
| Change the amount cap | `guardrails.py` → `MAX_AMOUNT` |
| Change route fees | `routes.py` → `fee_pct` / `fixed_fee` |
| Change AI model | `agent.py` → `model=` in `parse_intent()` |
| Add blocked phrases | `guardrails.py` → `BLOCKED_PHRASES` |
