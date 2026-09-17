"""Development stand-in for POST /invoke-tool.

This exists so the agent and UI can be built and rehearsed before Person B's
gateway is reachable. It is NOT an enforcement point and has no authority over
anything: it mirrors the shape of the contract and the published Cedar
thresholds so all three verdict states can be exercised locally.

At integration, only AgentFunction's GATEWAY_URL changes. Nothing here ships
into the enforcement path.
"""
import json
import os

# Mirrors gateway-policy/policies/policies/*.cedar. Kept here only so the
# local demo produces the same three outcomes the real policy store produces.
EXPENSE_LIMIT = 500
WIRE_LIMIT = 1000


def _evaluate(tool, params):
    """Return (decision, reason) the way the published Cedar policy set would."""
    if tool == "delete_customer_record":
        return "DENY", "Deleting a customer record is forbidden without exception."

    if tool == "approve_expense":
        amount = params.get("amount")
        if not isinstance(amount, (int, float)):
            return "DENY", "approve_expense requires a numeric amount."
        if amount <= 0:
            return "DENY", "An expense amount must be greater than zero."
        if amount > EXPENSE_LIMIT:
            return "DENY", f"Reimbursements above ${EXPENSE_LIMIT:,} are forbidden. Attempted ${amount:,.0f}."
        return "ALLOW", f"${amount:,.0f} is within the ${EXPENSE_LIMIT:,} reimbursement limit."

    if tool == "send_wire_transfer":
        amount = params.get("amount")
        if not isinstance(amount, (int, float)):
            return "DENY", "send_wire_transfer requires a numeric amount."
        if amount <= 0:
            return "DENY", "A wire amount must be greater than zero."
        if amount > WIRE_LIMIT:
            return "DENY", f"Wire transfers above ${WIRE_LIMIT:,} are forbidden. Attempted ${amount:,.0f}."
        return "ALLOW", f"${amount:,.0f} is within the ${WIRE_LIMIT:,} wire transfer limit."

    return "DENY", f"Unknown tool: {tool!r}."


def handler(event, _context):
    try:
        request = json.loads(event.get("body") or "{}")
        tool = request["tool"]
        params = request.get("params") or {}
    except (KeyError, json.JSONDecodeError):
        return {
            "statusCode": 400,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"decision": "DENY", "reason": "Invalid invoke-tool payload."}),
        }

    mode = "ENFORCE" if os.environ.get("MOCK_MODE", "LOG_ONLY").upper() == "ENFORCE" else "LOG_ONLY"
    policy_decision, reason = _evaluate(tool, params)
    effective = policy_decision if mode == "ENFORCE" else "ALLOW"
    if mode == "LOG_ONLY" and policy_decision == "DENY":
        reason = f"{reason} [LOG_ONLY mode: not blocked]"

    body = {"decision": effective, "reason": reason, "mode": mode, "policyDecision": policy_decision}
    if effective == "ALLOW":
        body["result"] = {"tool": tool, "params": params, "note": "Mock gateway — no data was written."}

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
