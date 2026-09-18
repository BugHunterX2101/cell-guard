"""Mode-control Lambda — lets the demo UI flip LOG_ONLY <-> ENFORCE live,
without a terminal open. Scoped to exactly one SSM parameter (see
template.yaml's ModeControlFunction Policies) and nothing else — it cannot
read or write anything the gateway or tool Lambdas touch.

This endpoint has no bearing on Cedar's decision-making. It only changes
which decision the gateway Lambda *honors* (see gateway/app.py's
effective_decision logic) — flipping it can never let a request bypass
Cedar's evaluation, only change whether a DENY is enforced or just logged.
"""
import json
import os

import boto3

ssm = boto3.client("ssm")
PARAMETER_NAME = os.environ["MODE_PARAMETER_NAME"]
VALID_MODES = ("LOG_ONLY", "ENFORCE")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _current_mode() -> str:
    try:
        value = ssm.get_parameter(Name=PARAMETER_NAME)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return "LOG_ONLY"
    return value if value in VALID_MODES else "LOG_ONLY"


def handler(event, _context):
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

        if method == "GET":
            return _response(200, {"mode": _current_mode()})

        if method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _response(400, {"error": "Malformed JSON body."})

            requested = body.get("mode")
            if requested not in VALID_MODES:
                return _response(400, {"error": f"mode must be one of {list(VALID_MODES)}."})

            ssm.put_parameter(Name=PARAMETER_NAME, Value=requested, Type="String", Overwrite=True)
            return _response(200, {"mode": requested})

        return _response(405, {"error": "Method not allowed."})
    except Exception as exc:  # noqa: BLE001 - fail closed, never leak internals
        return _response(500, {"error": f"Mode control error: {exc}"})
