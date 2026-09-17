"""approve_expense tool Lambda.

Invoked only by the gateway Lambda, only after an ALLOW. Writes an approval
record to the shared app-data table. Does not re-check authorization — the
gateway is the single enforcement point (see NFR: "Cedar's decision is the
gate, not IAM alone" — this function's own IAM role has no permission beyond
writing this one item shape).
"""

import os
import time
import uuid
from decimal import Decimal

import boto3

_table = boto3.resource("dynamodb").Table(os.environ["APP_TABLE_NAME"])


def handler(event, context):
    params = event.get("params") or {}
    amount = params["amount"]
    employee_id = params["employee_id"]

    approval_id = str(uuid.uuid4())
    _table.put_item(
        Item={
            "pk": f"EXPENSE#{approval_id}",
            "sk": "META",
            "record_type": "expense_approval",
            "approval_id": approval_id,
            "employee_id": employee_id,
            # DynamoDB's Table resource rejects native floats outright.
            "amount": Decimal(str(amount)) if isinstance(amount, float) else amount,
            "status": "approved",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    return {"approval_id": approval_id, "status": "approved", "amount": amount, "employee_id": employee_id}
