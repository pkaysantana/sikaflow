"""
Execution layer: real onchain settlement on Base Sepolia.

If AGENT_PRIVATE_KEY and BASE_SEPOLIA_RPC are configured:
  → Signs and broadcasts a real transaction on Base Sepolia
  → Returns the real transaction hash and BaseScan URL

Otherwise:
  → Falls back to a deterministic simulated hash, clearly labelled

Why onchain execution matters for autonomous agents:
  Traditional banking rails require a human to authorise every transfer.
  There is no mechanism for software to initiate a bank payment
  unilaterally — every step requires manual sign-off from an operator.

  An agent with a wallet changes this. It can hold stable-value assets,
  initiate transfers, and settle across borders without waiting for
  business hours or operator approval. The agent acts.

  Base is used because it is low-cost, fast, and EVM-compatible.

Execution asset (demo): native ETH on Base Sepolia — 0.00001 ETH per transfer.
This is a proof-of-execution: a real on-chain transaction that produces a
verifiable tx hash. Value accounting is tracked in GBP in the coordination layer.
In a production deployment, the execution asset would be USDC or another
stable-value token transferred to the recipient's resolved wallet.
"""

import os
import hashlib
import time
from dataclasses import dataclass, asdict
from routes import ExecutionPath, calculate_fee

NETWORK               = "Base Sepolia"
EXECUTION_ASSET_LIVE  = "ETH (execution proof)"   # what is actually sent on-chain in this demo
EXPLORER_BASE         = "https://sepolia.basescan.org/tx/"
BASE_SEPOLIA_ID = 84532

# Symbolic proof-of-execution: 0.00001 ETH (essentially free on testnet)
EXECUTION_PROOF_WEI = 10_000_000_000_000

# Destination allowlist — each maps to a real wallet on Base Sepolia.
# Override any address via environment variable before the demo.
DESTINATION_WALLETS: dict[str, str] = {
    "ghana":    os.getenv("GHANA_WALLET",   "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"),
    "nigeria":  os.getenv("NIGERIA_WALLET", "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"),
    "kenya":    os.getenv("KENYA_WALLET",   "0x90F79bf6EB2c4f870365E785982E1f101E93b906"),
    "savings":  os.getenv("SAVINGS_WALLET", "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"),
    "family":   os.getenv("FAMILY_WALLET",  "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"),
    "friend":   os.getenv("FRIEND_WALLET",  "0x976EA74026E726554dB657fA54763abd0C3a0aa9"),
    "wallet":   os.getenv("SAVINGS_WALLET", "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"),
    "transfer": os.getenv("NIGERIA_WALLET", "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"),
    "ledger":   os.getenv("SAVINGS_WALLET", "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"),
}


@dataclass
class ExecutionReceipt:
    network:           str
    asset:             str       # what was actually sent on-chain
    agent_wallet:      str
    destination:       str       # resolved wallet address
    destination_label: str       # human label (e.g. "Ghana")
    amount_gbp:        float     # coordinated value intent (GBP)
    fee_gbp:           float
    received_gbp:      float
    route_name:        str
    estimated_time:    str
    tx_hash:           str
    tx_url:            str       # empty string if simulated
    status:            str       # "CONFIRMED" | "SIMULATED" | "ERROR"
    execution_mode:    str       # "LIVE ONCHAIN" | "SIMULATED"
    simulated:         bool

    def to_dict(self) -> dict:
        return asdict(self)


def _get_agent_address() -> str:
    key = os.getenv("AGENT_PRIVATE_KEY")
    if key:
        try:
            from eth_account import Account
            return Account.from_key(key).address
        except Exception:
            pass
    return "0xAgentWallet_NOT_CONFIGURED"


def _attempt_real_tx(to_address: str) -> str | None:
    """
    Attempt a real Base Sepolia transaction.
    Returns the tx hash string, or None if execution is not configured or fails.
    """
    private_key = os.getenv("AGENT_PRIVATE_KEY")
    rpc_url     = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")

    if not private_key:
        return None

    try:
        from web3 import Web3
        from eth_account import Account

        w3      = Web3(Web3.HTTPProvider(rpc_url))
        account = Account.from_key(private_key)

        nonce = w3.eth.get_transaction_count(account.address)
        tx = {
            "nonce":    nonce,
            "to":       Web3.to_checksum_address(to_address),
            "value":    EXECUTION_PROOF_WEI,
            "gas":      21000,
            "gasPrice": w3.eth.gas_price,
            "chainId":  BASE_SEPOLIA_ID,
        }

        signed   = account.sign_transaction(tx)
        raw_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        h        = raw_hash.hex()
        return h if h.startswith("0x") else "0x" + h

    except Exception as e:
        print(f"  [execution] Real tx failed: {e}")
        return None


def _sim_hash(destination: str, amount: float) -> str:
    seed   = f"{destination}:{amount}:{int(time.time())}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:16].upper()
    return f"0xSIM_{digest}"


def execute_transfer(path: ExecutionPath, amount: float, destination: str) -> ExecutionReceipt:
    """
    Execute a transfer on the selected rail.

    For onchain rails: attempts a real Base Sepolia transaction.
    Falls back to simulation if AGENT_PRIVATE_KEY is not set or tx fails.
    """
    fee           = calculate_fee(path, amount)
    received      = round(amount - fee, 2)
    dest_lower    = (destination or "").lower().strip()
    dest_label    = destination.capitalize() if destination else "—"
    agent_address = _get_agent_address()

    # Resolve destination to wallet address
    to_address = DESTINATION_WALLETS.get(dest_lower)

    tx_hash   = None
    simulated = True

    # Attempt real execution for onchain rail only
    if path.rail_type == "onchain" and to_address:
        tx_hash = _attempt_real_tx(to_address)
        if tx_hash:
            simulated = False

    if not tx_hash:
        tx_hash    = _sim_hash(destination, amount)
        to_address = to_address or f"0x{dest_lower.upper()[:8]}_SIM"

    tx_url = (EXPLORER_BASE + tx_hash) if not simulated else ""

    # Network and asset depend on rail type
    if path.rail_type == "onchain":
        network, asset = NETWORK, ASSET
    elif path.rail_type == "internal":
        network, asset = "Internal Ledger", "GBP"
    else:
        network, asset = "SWIFT/SEPA", "GBP"

    return ExecutionReceipt(
        network           = network,
        asset             = asset,
        agent_wallet      = agent_address,
        destination       = to_address,
        destination_label = dest_label,
        amount_gbp        = amount,
        fee_gbp           = fee,
        received_gbp      = received,
        route_name        = path.name,
        estimated_time    = path.time_estimate,
        tx_hash           = tx_hash,
        tx_url            = tx_url,
        status            = "CONFIRMED" if not simulated else "SIMULATED",
        simulated         = simulated,
    )
