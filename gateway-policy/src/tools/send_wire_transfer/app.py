"""send_wire_transfer tool Lambda.

Invoked only by the gateway Lambda, only after an ALLOW. Writes a transfer
record to the shared app-data table.
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
    recipient = params["recipient"]

    transfer_id = str(uuid.uuid4())
    _table.put_item(
        Item={
            "pk": f"TRANSFER#{transfer_id}",
            "sk": "META",
            "record_type": "wire_transfer",
            "transfer_id": transfer_id,
            "recipient": recipient,
            # DynamoDB's Table resource rejects native floats outright.
            "amount": Decimal(str(amount)) if isinstance(amount, float) else amount,
            "status": "sent",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    return {"transfer_id": transfer_id, "status": "sent", "amount": amount, "recipient": recipient}
