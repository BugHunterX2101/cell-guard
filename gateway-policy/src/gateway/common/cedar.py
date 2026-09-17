"""Shared helpers for building embedded-Cedar authorization requests.

Kept in one place so the gateway Lambda builds entity/context shapes the
same way the Cedar schema (policies/schema.json) expects them. Authorization
runs via the embedded `cedarpy` engine (see common/engine.py) rather than
the managed Amazon Verified Permissions service — see engine.py's docstring
for why.
"""

NAMESPACE = "CellGuard"

# Cedar action id + the context fields it requires, keyed by the wire-level
# tool name used in the /invoke-tool contract. These mirror policies/schema.json.
TOOL_ACTIONS = {
    "approve_expense": {
        "actionId": "ApproveExpense",
        "context_fields": ["amount", "employeeId", "sessionId", "source"],
    },
    "delete_customer_record": {
        "actionId": "DeleteCustomerRecord",
        "context_fields": ["customerId", "sessionId", "source"],
    },
    "send_wire_transfer": {
        "actionId": "SendWireTransfer",
        "context_fields": ["amount", "recipient", "sessionId", "source"],
    },
}

# Mirrors the fixed thresholds encoded in policies/policies/*.cedar. Used only
# to produce a human-readable reason string for the API response and audit
# log — the actual allow/deny decision always comes from the Cedar engine,
# never from this dict.
THRESHOLDS = {
    "approve_expense": 500,
    "send_wire_transfer": 1000,
}


def _coerce(value):
    """Normalize a Python value for a Cedar context field.

    Raises ValueError (not TypeError) on anything unsupported so callers in
    the gateway handler can turn it into a clean 400 response instead of an
    unhandled 500 — a malformed request from the agent should never crash
    the gateway.

    A whole-number float is coerced to int: cedarpy's plain-dict context
    does NOT auto-coerce floats into a schema-declared Long field — passing
    120.0 for a Long fails with Decision.NoDecision ("failed to parse
    schema from request") rather than being treated as 120. Confirmed
    against the real engine.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"Cedar Long context fields must be whole numbers, got {value}")
        return int(value)
    if isinstance(value, str):
        return value
    raise ValueError(f"Unsupported context attribute type: {type(value)!r}")


def build_principal(user_id: str) -> dict:
    return {"type": f"{NAMESPACE}::Agent", "id": user_id}


def build_resource(tool_name: str) -> dict:
    return {"type": f"{NAMESPACE}::Tool", "id": tool_name}


def build_action(tool_name: str) -> dict:
    return {"type": f"{NAMESPACE}::Action", "id": TOOL_ACTIONS[tool_name]["actionId"]}


def build_context(tool_name: str, params: dict, request_context: dict) -> dict:
    """Assemble the Cedar context dict for a tool call from params + request context.

    Only the fields the Cedar schema declares for this action are included —
    passing an undeclared field fails strict schema validation.
    """
    merged = {
        "amount": params.get("amount"),
        "employeeId": params.get("employee_id"),
        "customerId": params.get("customer_id"),
        "recipient": params.get("recipient"),
        "sessionId": request_context.get("session_id"),
        "source": request_context.get("source"),
    }
    fields = TOOL_ACTIONS[tool_name]["context_fields"]
    context = {}
    for field in fields:
        value = merged.get(field)
        if value is None:
            raise ValueError(f"Missing required field for {tool_name}: {field}")
        context[field] = _coerce(value)
    return context


def build_reason(decision: str, tool_name: str, params: dict) -> str:
    """Human-readable explanation of the Cedar decision for the API response.

    This text is presentation only — the enforcement decision itself is
    produced entirely by the embedded Cedar engine, never by this function.
    """
    if tool_name == "delete_customer_record":
        if decision == "DENY":
            return "Policy forbids delete_customer_record unconditionally."
        return "Policy permits this action."

    threshold = THRESHOLDS.get(tool_name)
    amount = params.get("amount")
    if decision == "DENY":
        if isinstance(amount, (int, float)) and amount <= 0:
            return f"Policy forbids {tool_name} with a non-positive amount (attempted: ${amount})."
        return (
            f"Policy forbids {tool_name} above the ${threshold} threshold "
            f"(attempted amount: ${amount})."
        )
    return f"Policy permits {tool_name}: amount ${amount} is within the ${threshold} threshold."
