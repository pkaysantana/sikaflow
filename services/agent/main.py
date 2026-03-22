"""
Sikaflow – Autonomous Financial Coordination Agent
CLI entry point.

Usage:
    python main.py
"""

from agent import parse_intent
from routes import select_route, calculate_fee
from guardrails import check

BANNER = """
╔══════════════════════════════════════════════╗
║        SIKAFLOW  –  Financial Agent          ║
║   "Sika" means money in Twi (Ghana)          ║
╚══════════════════════════════════════════════╝
Type your instruction, or 'quit' to exit.
Examples:
  • Send £50 to Ghana
  • Split £100 between savings and family
  • Transfer £200 to Nigeria via stablecoin
"""

DIVIDER = "─" * 48


def print_section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def run_single_transfer(intent: dict, raw_input: str):
    """Handle a straightforward send/transfer intent."""
    amount = intent.get("amount")
    destination = intent.get("destination") or ""

    # --- Guardrails ---
    safe, reason = check(intent, raw_input)
    if not safe:
        print_section("🚫  GUARDRAIL TRIGGERED")
        print(f"  {reason}")
        return

    # --- Route Selection ---
    best, alt = select_route(amount, destination)
    best_fee = calculate_fee(best, amount)
    savings = None
    if alt:
        alt_fee = calculate_fee(alt, amount)
        savings = round(alt_fee - best_fee, 2)

    # --- Output ---
    print_section("✅  AGENT DECISION")
    print(f"  Reasoning : {intent.get('reasoning', '—')}")
    print(f"  Action    : {intent.get('action', '—').upper()}")
    print(f"  Amount    : £{amount:.2f}")
    print(f"  To        : {destination or '—'}")

    print_section("🚀  EXECUTION PLAN")
    print(f"  Route     : {best.name}")
    print(f"  Method    : {best.description}")
    print(f"  Fee       : £{best_fee:.2f}")
    print(f"  Est. Time : {best.time_estimate}")

    if savings and savings > 0:
        print(f"\n  💰 Savings vs {alt.name}: £{savings:.2f}")

    print_section("📋  SIMULATION COMPLETE")
    print(f"  Amount sent    : £{amount:.2f}")
    print(f"  Fee deducted   : £{best_fee:.2f}")
    print(f"  Recipient gets : £{amount - best_fee:.2f}")
    print(f"  Status         : ✓ Simulated (no real funds moved)")


def run_split(intent: dict, raw_input: str):
    """Handle a split payment intent."""
    splits = intent.get("split") or []
    total = sum(s.get("amount", 0) for s in splits)

    # Build a combined intent for guardrails (total amount)
    combined = {**intent, "amount": total, "destination": None}
    safe, reason = check(combined, raw_input)
    if not safe:
        print_section("🚫  GUARDRAIL TRIGGERED")
        print(f"  {reason}")
        return

    print_section("✅  AGENT DECISION  –  SPLIT")
    print(f"  Reasoning : {intent.get('reasoning', '—')}")
    print(f"  Total     : £{total:.2f}")
    print(f"  Legs      : {len(splits)}")

    total_fees = 0.0
    for leg in splits:
        dest = leg.get("destination", "unknown")
        amt = leg.get("amount", 0)
        leg_intent = {"action": "send", "amount": amt, "destination": dest}
        leg_safe, leg_reason = check(leg_intent, raw_input)

        print(f"\n  ── Leg: {dest}  £{amt:.2f} ──")
        if not leg_safe:
            print(f"     ⚠️  Skipped: {leg_reason}")
            continue

        best, alt = select_route(amt, dest)
        fee = calculate_fee(best, amt)
        total_fees += fee
        print(f"     Route : {best.name}")
        print(f"     Fee   : £{fee:.2f}  |  Time: {best.time_estimate}")
        print(f"     Recv  : £{amt - fee:.2f}")

    print_section("📋  SPLIT SUMMARY")
    print(f"  Total sent   : £{total:.2f}")
    print(f"  Total fees   : £{total_fees:.2f}")
    print(f"  Net paid out : £{total - total_fees:.2f}")
    print(f"  Status       : ✓ Simulated (no real funds moved)")


def process(user_input: str):
    print("\n⏳  Parsing intent...")
    intent = parse_intent(user_input)
    action = intent.get("action", "unknown")

    if action == "unknown" or intent.get("amount") is None:
        print_section("❓  COULD NOT UNDERSTAND")
        print(f"  {intent.get('reasoning', 'Please rephrase your instruction.')}")
        return

    if action == "split" and intent.get("split"):
        run_split(intent, user_input)
    else:
        run_single_transfer(intent, user_input)


def main():
    print(BANNER)
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        process(user_input)


if __name__ == "__main__":
    main()
