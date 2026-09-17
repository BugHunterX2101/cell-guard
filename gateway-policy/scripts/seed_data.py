#!/usr/bin/env python3
"""Seed a couple of sample customer records so delete_customer_record has a
real row to (attempt to) delete during the demo. Optional — the tool Lambda
works fine against an empty table, but "here's a customer, watch it survive
the attack" is a stronger visual than an empty DynamoDB console.

Usage: python3 scripts/seed_data.py [table-name]
"""

import sys
import time

import boto3

TABLE_NAME = sys.argv[1] if len(sys.argv) > 1 else "cellguard-gateway-app-data"

SAMPLE_CUSTOMERS = [
    {"customer_id": "cust-1001", "name": "Ada Lovelace", "email": "ada@example.com"},
    {"customer_id": "cust-1002", "name": "Grace Hopper", "email": "grace@example.com"},
]


def main() -> None:
    table = boto3.resource("dynamodb").Table(TABLE_NAME)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for customer in SAMPLE_CUSTOMERS:
        table.put_item(
            Item={
                "pk": f"CUSTOMER#{customer['customer_id']}",
                "sk": "META",
                "record_type": "customer",
                "created_at": now,
                **customer,
            }
        )
        print(f"Seeded {customer['customer_id']} ({customer['name']})")


if __name__ == "__main__":
    main()
