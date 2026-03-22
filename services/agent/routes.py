"""
Execution paths: available rails and selection logic.

Rail types:
  onchain     — Base L2, executable by the agent wallet without human
                authorisation at each step; demo uses ETH as execution proof
  traditional — SWIFT/SEPA correspondent banking, requires intermediary
                authorisation and is not autonomously executable
  internal    — Same-platform ledger, instant and zero-cost
"""

from dataclasses import dataclass


@dataclass
class ExecutionPath:
    name: str
    description: str
    fee_pct: float       # percentage of transfer amount
    fixed_fee: float     # GBP
    time_estimate: str
    rail_type: str       # "onchain" | "traditional" | "internal"


EXECUTION_PATHS = [
    ExecutionPath(
        name="Traditional Bank Rail",
        description="SWIFT/SEPA correspondent banking — requires intermediary authorisation",
        fee_pct=0.025,
        fixed_fee=2.50,
        time_estimate="1–3 business days",
        rail_type="traditional",
    ),
    ExecutionPath(
        name="Base Onchain",
        description="Programmable settlement on Base L2 — agent-executable without manual authorisation",
        fee_pct=0.005,
        fixed_fee=0.50,
        time_estimate="< 5 minutes",
        rail_type="onchain",
    ),
    ExecutionPath(
        name="Internal Ledger",
        description="Same-platform ledger transfer — instant, zero cost",
        fee_pct=0.0,
        fixed_fee=0.0,
        time_estimate="Instant",
        rail_type="internal",
    ),
]


def calculate_fee(path: ExecutionPath, amount: float) -> float:
    return round(amount * path.fee_pct + path.fixed_fee, 2)


def select_path(amount: float, destination: str) -> tuple[ExecutionPath, ExecutionPath | None]:
    """
    Select the optimal execution path for the transfer.

    Logic:
    - Internal destinations (savings, wallet) → Internal Ledger
    - All other destinations → ranked by cost; Base Onchain wins on price
      and is preferred because it is agent-executable without human sign-off

    Returns (best_path, alternative_path).
    """
    dest = (destination or "").lower().strip()

    if dest in ("savings", "wallet", "ledger"):
        best = next(p for p in EXECUTION_PATHS if p.rail_type == "internal")
        alt  = next(p for p in EXECUTION_PATHS if p.rail_type == "onchain")
        return best, alt

    candidates = [p for p in EXECUTION_PATHS if p.rail_type != "internal"]
    candidates.sort(key=lambda p: calculate_fee(p, amount))
    best = candidates[0]
    alt  = candidates[1] if len(candidates) > 1 else None
    return best, alt
