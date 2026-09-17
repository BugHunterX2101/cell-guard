#!/usr/bin/env python3
"""Create (or resync) the Cedar schema + policies in Amazon Verified Permissions.

Why a script instead of CloudFormation: AWS::VerifiedPermissions::Policy
requires the Cedar statement inlined as a template property, which would mean
maintaining the same policy text in two places (the .cedar file and the
template) and them drifting apart. This script treats policies/schema.json
and policies/policies/*.cedar as the single source of truth and pushes them
straight to AVP, which is also far faster to iterate on during the build than
a full stack update — edit a .cedar file, rerun this script, done.

Usage:
    python scripts/deploy_policies.py

Idempotent: reuses the policy store recorded in .policy-store-id if present,
otherwise creates one and records its ID there. Every run fully resyncs the
schema and replaces all policies in the store with exactly what's in
policies/policies/*.cedar (fine at this scale: 4-5 policies for a demo).

Prints the policy store ID on success — pass it to `sam deploy` as the
PolicyStoreId parameter (see scripts/deploy.sh, which does this for you).
"""

import json
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "policies" / "schema.json"
POLICIES_DIR = ROOT / "policies" / "policies"
STATE_FILE = ROOT / ".policy-store-id"


def main() -> None:
    client = boto3.client("verifiedpermissions")

    policy_store_id = None
    if STATE_FILE.exists():
        policy_store_id = STATE_FILE.read_text().strip() or None

    if policy_store_id:
        try:
            client.get_policy_store(policyStoreId=policy_store_id)
            print(f"Reusing existing policy store: {policy_store_id}")
        except client.exceptions.ResourceNotFoundException:
            print(f"Recorded policy store {policy_store_id} no longer exists; creating a new one.")
            policy_store_id = None

    if not policy_store_id:
        created = client.create_policy_store(validationSettings={"mode": "STRICT"})
        policy_store_id = created["policyStoreId"]
        STATE_FILE.write_text(policy_store_id)
        print(f"Created policy store: {policy_store_id}")

    schema_json = SCHEMA_PATH.read_text()
    # Fail fast on invalid JSON before sending it to AVP.
    json.loads(schema_json)
    client.put_schema(policyStoreId=policy_store_id, definition={"cedarJson": schema_json})
    print("Schema applied.")

    existing = []
    paginator = client.get_paginator("list_policies")
    for page in paginator.paginate(policyStoreId=policy_store_id):
        existing.extend(page["policies"])
    for policy in existing:
        client.delete_policy(policyStoreId=policy_store_id, policyId=policy["policyId"])
    if existing:
        print(f"Removed {len(existing)} existing polic{'y' if len(existing) == 1 else 'ies'}.")

    cedar_files = sorted(POLICIES_DIR.glob("*.cedar"))
    if not cedar_files:
        print(f"No .cedar files found in {POLICIES_DIR}", file=sys.stderr)
        sys.exit(1)

    for cedar_file in cedar_files:
        statement = cedar_file.read_text()
        client.create_policy(
            policyStoreId=policy_store_id,
            definition={"static": {"description": cedar_file.stem, "statement": statement}},
        )
        print(f"Created policy from {cedar_file.name}")

    print(f"\nPolicy store ready: {policy_store_id}")
    print(f"(recorded in {STATE_FILE})")


if __name__ == "__main__":
    main()
