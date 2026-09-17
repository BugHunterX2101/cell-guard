"""Gateway Lambda — the single enforcement point for POST /invoke-tool.

Every tool call from the agent lands here first. This Lambda:
  1. Validates the request against the locked contract.
  2. Asks Amazon Verified Permissions for a real ALLOW/DENY on the actual
     parameters attempted (not on anything the agent was told to do).
  3. In ENFORCE mode, honors that decision — a DENY never reaches the tool.
     In LOG_ONLY mode, the decision is recorded but the tool still runs,
     which is what lets the demo show the same attack succeeding under one
     mode and failing under the other.
  4. Writes one audit entry per attempt regardless of outcome.

The agent side never calls a tool Lambda directly — this function is the
only thing with permission to invoke them (see template.yaml IAM policies).
"""

import json
import os

import boto3

from common.audit import write_audit_entry
from common.cedar import (
    build_action,
    build_context,
    build_principal,
    build_reason,
    build_resource,
    TOOL_ACTIONS,
)
from common.mode import get_mode

_avp = boto3.client("verifiedpermissions")
_lambda = boto3.client("lambda")

_POLICY_STORE_ID = os.environ["POLICY_STORE_ID"]

_TOOL_FUNCTION_NAMES = {
    "approve_expense": os.environ["APPROVE_EXPENSE_FUNCTION_NAME"],
    "delete_customer_record": os.environ["DELETE_CUSTOMER_RECORD_FUNCTION_NAME"],
    "send_wire_transfer": os.environ["SEND_WIRE_TRANSFER_FUNCTION_NAME"],
}


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _deny(reason: str, status_code: int = 200) -> dict:
    return _response(status_code, {"decision": "DENY", "reason": reason})


def _invoke_tool(tool_name: str, params: dict) -> dict:
    function_name = _TOOL_FUNCTION_NAMES[tool_name]
    invoke_response = _lambda.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"params": params}).encode("utf-8"),
    )
    payload = json.loads(invoke_response["Payload"].read() or b"{}")
    if invoke_response.get("FunctionError"):
        raise RuntimeError(f"Tool {tool_name} failed: {payload}")
    return payload


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _deny("Malformed JSON body.", status_code=400)

    tool_name = body.get("tool")
    params = body.get("params") or {}
    principal_in = body.get("principal") or {}
    request_context = body.get("context") or {}

    if tool_name not in TOOL_ACTIONS:
        return _deny(f"Unknown tool: {tool_name!r}.", status_code=400)

    user_id = principal_in.get("user_id")
    if not user_id:
        return _deny("Missing principal.user_id.", status_code=400)

    try:
        avp_context = build_context(tool_name, params, request_context)
    except ValueError as exc:
        return _deny(str(exc), status_code=400)

    principal = build_principal(user_id)
    resource = build_resource(tool_name)
    action = build_action(tool_name)

    avp_response = _avp.is_authorized(
        policyStoreId=_POLICY_STORE_ID,
        principal=principal,
        action=action,
        resource=resource,
        context=avp_context,
    )
    cedar_decision = avp_response["decision"]
    determining_policy_ids = [p["policyId"] for p in avp_response.get("determiningPolicies", [])]
    reason = build_reason(cedar_decision, tool_name, params)

    mode = get_mode()
    # ENFORCE honors Cedar's decision. LOG_ONLY always lets the call through —
    # that gap between "what was decided" and "what happened" is the point.
    effective_decision = cedar_decision if mode == "ENFORCE" else "ALLOW"
    if mode == "LOG_ONLY" and cedar_decision == "DENY":
        reason = f"{reason} [LOG_ONLY mode: not blocked]"

    result = None
    tool_executed = False
    if effective_decision == "ALLOW":
        try:
            result = _invoke_tool(tool_name, params)
            tool_executed = True
        except Exception as exc:  # noqa: BLE001 - surfaced to caller, still audited below
            write_audit_entry(
                tool=tool_name,
                params=params,
                principal=principal_in,
                request_context=request_context,
                cedar_decision=cedar_decision,
                effective_decision=effective_decision,
                mode=mode,
                reason=f"Tool execution failed: {exc}",
                determining_policy_ids=determining_policy_ids,
                tool_executed=False,
            )
            return _response(502, {"decision": "DENY", "reason": f"Tool execution failed: {exc}"})

    write_audit_entry(
        tool=tool_name,
        params=params,
        principal=principal_in,
        request_context=request_context,
        cedar_decision=cedar_decision,
        effective_decision=effective_decision,
        mode=mode,
        reason=reason,
        determining_policy_ids=determining_policy_ids,
        tool_executed=tool_executed,
    )

    response_body = {"decision": effective_decision, "reason": reason}
    if effective_decision == "ALLOW":
        response_body["result"] = result
    # Extra, non-breaking fields for debugging via curl/Postman and for the
    # demo UI to show the underlying policy decision even in LOG_ONLY mode.
    response_body["mode"] = mode
    response_body["policyDecision"] = cedar_decision
    return _response(200, response_body)
