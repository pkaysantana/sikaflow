"""
Routes: defines available transfer corridors and selects the optimal one.
"""

from dataclasses import dataclass


@dataclass
class Route:
    name: str
    description: str
    fee_pct: float        # percentage of amount
    fixed_fee: float      # GBP
    time_estimate: str
    method: str           # "bank" | "stablecoin" | "internal"


ROUTES = [
    Route(
        name="Direct Bank Transfer",
        description="Traditional SWIFT/SEPA bank route",
        fee_pct=0.025,       # 2.5%
        fixed_fee=2.50,
        time_estimate="1–3 business days",
        method="bank",
    ),
    Route(
        name="Stablecoin Route (USDC)",
        description="Convert to USDC on-chain, settle at destination",
        fee_pct=0.005,       # 0.5%
        fixed_fee=0.50,
        time_estimate="< 5 minutes",
        method="stablecoin",
    ),
    Route(
        name="Internal Wallet Transfer",
        description="Sikaflow internal ledger (same-platform users)",
        fee_pct=0.0,
        fixed_fee=0.0,
        time_estimate="Instant",
        method="internal",
    ),
]


def calculate_fee(route: Route, amount: float) -> float:
    return round(amount * route.fee_pct + route.fixed_fee, 2)


def select_route(amount: float, destination: str) -> tuple[Route, Route | None]:
    """
    Returns (best_route, alternative_route).
    Picks cheapest route; excludes internal route unless destination is 'wallet'.
    """
    destination_lower = (destination or "").lower()

    if destination_lower in ("wallet", "savings"):
        best = next(r for r in ROUTES if r.method == "internal")
        alt = next(r for r in ROUTES if r.method == "stablecoin")
        return best, alt

    candidates = [r for r in ROUTES if r.method != "internal"]
    candidates.sort(key=lambda r: calculate_fee(r, amount))
    best = candidates[0]
    alt = candidates[1] if len(candidates) > 1 else None
    return best, alt
