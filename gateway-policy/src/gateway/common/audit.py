"""Audit log writer — one item per tool-call attempt, ALLOW or DENY alike."""

import os
import time
import uuid
from decimal import Decimal

import boto3

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(os.environ["AUDIT_TABLE_NAME"])


def _dynamo_safe(value):
    """Recursively convert floats to Decimal — boto3's Table resource raises
    on native Python floats, and `params` here is passed through verbatim
    from the request body, so it may contain one."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _dynamo_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dynamo_safe(v) for v in value]
    return value


def write_audit_entry(
    *,
    tool: str,
    params: dict,
    principal: dict,
    request_context: dict,
    cedar_decision: str,
    effective_decision: str,
    mode: str,
    reason: str,
    determining_policy_ids: list,
    tool_executed: bool,
) -> None:
    now = time.time()
    item = {
        "pk": "AUDIT",
        # zero-padded epoch millis keeps lexicographic sort == chronological sort
        "sk": f"{int(now * 1000):016d}#{uuid.uuid4()}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "tool": tool,
        "params": _dynamo_safe(params),
        "principal": principal,
        "session_id": request_context.get("session_id"),
        "source": request_context.get("source"),
        "cedar_decision": cedar_decision,
        "effective_decision": effective_decision,
        "mode": mode,
        "reason": reason,
        "determining_policy_ids": determining_policy_ids,
        "tool_executed": tool_executed,
    }
    _table.put_item(Item=item)
