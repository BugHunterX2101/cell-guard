#!/usr/bin/env python3
"""Stage and validate the Cedar schema + policies before a deploy.

policies/schema.json and policies/policies/*.cedar are the single
edited-by-humans source of truth. This script:

  1. Copies them into src/gateway/policies/ — the gateway Lambda's own
     common/engine.py loads them from there at cold start (SAM's CodeUri is
     a single directory boundary, so the Lambda package can't reach files
     outside src/gateway/ directly). The copy is a pure build artifact,
     regenerated fresh on every run and gitignored — never hand-edited.
  2. Validates the schema and policies against the real Cedar engine
     (cedarpy — the same engine the gateway Lambda embeds) before they ever
     reach a deploy, so a typo in a .cedar file fails fast here instead of
     surfacing as a Lambda cold-start crash after `sam deploy` succeeds.

Previously this script instead pushed the schema/policies to an Amazon
Verified Permissions policy store. That service is blocked account-wide on
the AWS account this was built against (see common/engine.py's docstring
for the full story), so authorization now runs via the embedded Cedar
engine and this script's job shrank to "stage + validate locally" — no AWS
credentials or network calls needed at all.

Usage:
    python scripts/prepare_policies.py
"""

import shutil
import sys
from pathlib import Path

import cedarpy

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "policies" / "schema.json"
POLICIES_DIR = ROOT / "policies" / "policies"
STAGED_DIR = ROOT / "src" / "gateway" / "policies"


def main() -> None:
    if STAGED_DIR.exists():
        shutil.rmtree(STAGED_DIR)
    shutil.copytree(POLICIES_DIR.parent, STAGED_DIR)
    print(f"Staged policies/ -> {STAGED_DIR}")

    schema_json = SCHEMA_PATH.read_text()
    schema = cedarpy.Schema.from_json_str(schema_json)
    print("[OK] schema.json parses as valid Cedar JSON schema")

    cedar_files = sorted(POLICIES_DIR.glob("*.cedar"))
    if not cedar_files:
        print(f"No .cedar files found in {POLICIES_DIR}", file=sys.stderr)
        sys.exit(1)
    combined = "\n\n".join(f.read_text() for f in cedar_files)

    cedarpy.PolicySet.from_str(combined)
    print(f"[OK] all {len(cedar_files)} .cedar files parse as valid Cedar policy syntax")

    validation = cedarpy.validate_policies(combined, schema)
    if not validation.validation_passed:
        print("[FAIL] policy validation against schema failed:", file=sys.stderr)
        for err in validation.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    print("[OK] all policies validate against schema.json with zero errors")

    print("\nPolicies staged and validated. Safe to `sam build`.")


if __name__ == "__main__":
    main()
