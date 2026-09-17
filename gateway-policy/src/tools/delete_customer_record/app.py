"""delete_customer_record tool Lambda.

Invoked only by the gateway Lambda, only after an ALLOW. In this demo the
Cedar policy forbids this action unconditionally, so under ENFORCE mode this
code should never actually run — it exists so the LOG_ONLY path has a real
effect to point at ("it deleted the record, and here's the log entry saying
policy would have denied it").
"""

import os
import time

import boto3

_table = boto3.resource("dynamodb").Table(os.environ["APP_TABLE_NAME"])


def handler(event, context):
    params = event.get("params") or {}
    customer_id = params["customer_id"]

    _table.delete_item(Key={"pk": f"CUSTOMER#{customer_id}", "sk": "META"})
    _table.put_item(
        Item={
            "pk": f"CUSTOMER#{customer_id}",
            "sk": "DELETION_RECORD",
            "record_type": "customer_deletion",
            "customer_id": customer_id,
            "deleted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    return {"customer_id": customer_id, "status": "deleted"}
