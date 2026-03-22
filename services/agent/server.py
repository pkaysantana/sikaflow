"""
Web server: exposes the five-stage coordination pipeline over HTTP.

GET  /             → serves the web UI
POST /api/coordinate → runs the pipeline, returns JSON
"""

import os
import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent      import parse_intent
from routes     import select_path, calculate_fee
from execution  import execute_transfer, DESTINATION_WALLETS
from guardrails import inspect as policy_inspect, is_destination_allowed

app = FastAPI(title="Sikaflow")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CoordinationRequest(BaseModel):
    input: str


# ─── Serve UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html.read_text(encoding="utf-8"))


# ─── Coordinate endpoint ──────────────────────────────────────────────────────

@app.post("/api/coordinate")
async def coordinate(req: CoordinationRequest):
    try:
        result = run_pipeline(req.input.strip())
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def _plan_execution(intent: dict) -> dict | None:
    """
    Build an execution plan from parsed intent.
    Returns a dict with _path keys (ExecutionPath objects) for internal use,
    plus serializable fields for the API response.
    """
    action = intent.get("action", "unknown")
    amount = intent.get("amount")

    if not amount or action == "unknown":
        return None

    if action == "split" and intent.get("split"):
        legs = []
        for leg in intent["split"]:
            path, _ = select_path(leg["amount"], leg.get("destination", ""))
            fee     = calculate_fee(path, leg["amount"])
            legs.append({
                "destination": leg.get("destination", "unknown"),
                "amount":      leg["amount"],
                "_path":       path,           # internal only
                "path_name":   path.name,
                "rail_type":   path.rail_type,
                "fee":         fee,
                "description": path.description,
            })
        total      = sum(l["amount"] for l in legs)
        total_fees = sum(l["fee"]    for l in legs)
        return {
            "type":        "split",
            "legs":        legs,
            "total":       total,
            "total_fees":  total_fees,
            "summary":     f"Split £{total:.2f} across {len(legs)} legs",
        }

    destination = intent.get("destination") or ""
    path, alt   = select_path(amount, destination)
    fee         = calculate_fee(path, amount)
    alt_fee     = calculate_fee(alt, amount) if alt else None
    saving      = round(alt_fee - fee, 2) if alt_fee else 0
    return {
        "type":         "send",
        "amount":       amount,
        "destination":  destination,
        "_path":        path,              # internal only
        "path_name":    path.name,
        "rail_type":    path.rail_type,
        "description":  path.description,
        "alt_path_name": alt.name if alt else None,
        "fee":          fee,
        "alt_fee":      alt_fee,
        "saving":       saving,
        "summary":      (
            f"Send £{amount:.2f} to {destination.capitalize() or '—'}"
            f" via {path.name} (£{fee:.2f} fee)"
        ),
    }


def _run_execution(plan: dict) -> dict:
    """Execute the plan; uses internal _path objects."""
    if plan["type"] == "send":
        receipt = execute_transfer(plan["_path"], plan["amount"], plan["destination"])
        return {
            "status":           receipt.status,
            "network":          receipt.network,
            "asset":            receipt.asset,
            "agent_wallet":     receipt.agent_wallet,
            "destination":      receipt.destination,
            "destination_label": receipt.destination_label,
            "amount_gbp":       receipt.amount_gbp,
            "fee_gbp":          receipt.fee_gbp,
            "received_gbp":     receipt.received_gbp,
            "route_name":       receipt.route_name,
            "estimated_time":   receipt.estimated_time,
            "tx_hash":          receipt.tx_hash,
            "tx_url":           receipt.tx_url,
            "simulated":        receipt.simulated,
            "legs":             None,
        }

    # Split — execute each leg independently
    legs_out = []
    for leg in plan["legs"]:
        if not is_destination_allowed(leg["destination"]):
            legs_out.append({
                "status":      "SKIPPED",
                "destination": leg["destination"],
                "reason":      "destination not on policy allowlist",
            })
            continue
        r = execute_transfer(leg["_path"], leg["amount"], leg["destination"])
        legs_out.append({
            "status":           r.status,
            "destination":      r.destination,
            "destination_label": r.destination_label,
            "amount_gbp":       r.amount_gbp,
            "fee_gbp":          r.fee_gbp,
            "received_gbp":     r.received_gbp,
            "route_name":       r.route_name,
            "estimated_time":   r.estimated_time,
            "tx_hash":          r.tx_hash,
            "tx_url":           r.tx_url,
            "simulated":        r.simulated,
        })

    return {
        "status":       "COMPLETED",
        "network":      "Base Sepolia",
        "asset":        "USDC",
        "agent_wallet": legs_out[0].get("destination", "") if legs_out else "",
        "total_gbp":    plan["total"],
        "total_fees":   plan["total_fees"],
        "net_gbp":      round(plan["total"] - plan["total_fees"], 2),
        "legs":         legs_out,
        "tx_hash":      None,
        "tx_url":       None,
        "simulated":    True,
    }


def _serialize_plan(plan: dict | None) -> dict | None:
    """Strip internal _path keys before sending as JSON."""
    if plan is None:
        return None
    out = {k: v for k, v in plan.items() if not k.startswith("_")}
    if "legs" in out and out["legs"]:
        out["legs"] = [{k: v for k, v in leg.items() if not k.startswith("_")}
                       for leg in out["legs"]]
    return out


def run_pipeline(user_input: str) -> dict:
    # ── 1. Intent resolution ─────────────────────────────────────────────────
    intent = parse_intent(user_input)
    intent_data = {
        "action":      intent.get("action", "unknown"),
        "amount":      intent.get("amount"),
        "destination": intent.get("destination"),
        "split":       intent.get("split"),
        "reasoning":   intent.get("reasoning", ""),
    }

    # ── 2. Execution planning ─────────────────────────────────────────────────
    plan = None
    if intent_data["action"] != "unknown" and intent_data["amount"]:
        plan = _plan_execution(intent)

    # ── 3. Policy inspection ──────────────────────────────────────────────────
    policy_intent = intent.copy()
    if plan and plan.get("type") == "split":
        policy_intent = {**intent, "amount": plan["total"], "destination": None}

    report = policy_inspect(policy_intent, user_input)
    policy_data = {
        "approved": report["approved"],
        "reason":   report["reason"],
        "checks":   report["checks"],
    }

    # ── 4. Onchain execution (gated on policy approval) ───────────────────────
    execution_data = None
    if report["approved"] and plan:
        try:
            execution_data = _run_execution(plan)
        except Exception as e:
            execution_data = {"status": "ERROR", "error": str(e)}

    # ── 5. Audit record ───────────────────────────────────────────────────────
    ts = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    amt = intent_data.get("amount")
    dst = intent_data.get("destination") or "(split)"
    audit_data = {
        "timestamp": ts,
        "input":     user_input,
        "intent":    f"{intent_data['action'].upper()}  £{amt}  →  {dst}" if amt else "unresolved",
        "plan":      _serialize_plan(plan)["summary"] if plan else "none",
        "policy":    "APPROVED" if report["approved"] else f"BLOCKED — {report['reason']}",
        "execution": execution_data["status"] if execution_data else "HALTED",
    }

    return {
        "input":     user_input,
        "intent":    intent_data,
        "plan":      _serialize_plan(plan),
        "policy":    policy_data,
        "execution": execution_data,
        "audit":     audit_data,
    }


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
