"""Embedded Cedar authorization engine — replaces Amazon Verified Permissions.

Why embedded instead of AVP: on the AWS account this was built and deployed
against (a hackathon-provisioned sandbox account, see
https://www.wemakedevs.org/aws/first-commit), every Verified Permissions API
call — regardless of action, region, or the specific IAM permissions granted
— failed with `AccessDeniedException: "The AWS Access Key Id needs a
subscription for the service"`. That error shape (no named missing action,
identical across regions) points to an account/organization-level block
rather than a fixable IAM policy gap. Verified Permissions isn't mentioned
anywhere in the hackathon's rules, while Cedar itself is explicitly listed
as an endorsed technology ("Cedar: authorization as policy" under the Build
It track) — so this runs the same Cedar engine AVP is built on, via the
`cedarpy` Python bindings (the official Cedar Policy Rust engine), directly
inside the gateway Lambda instead of calling out to a managed service.

This is a pure swap of *where* Cedar evaluates policy, not what the
authorization model is: policies/schema.json and policies/policies/*.cedar
are unchanged, byte-for-byte, from the AVP-based design, and were validated
against this same engine before the swap (see scripts/prepare_policies.py).
It also removes a network hop from every tool call, which only helps the
"keep the gateway check fast" NFR.

Schema and policies are parsed once per Lambda execution environment (cold
start) and reused across warm invocations — cedarpy's documented pattern
for avoiding a re-parse on every request.
"""

from pathlib import Path

import cedarpy

_POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
_SCHEMA_PATH = _POLICIES_DIR / "schema.json"
_POLICY_FILES_DIR = _POLICIES_DIR / "policies"

_SCHEMA = cedarpy.Schema.from_json_str(_SCHEMA_PATH.read_text())

_policy_files = sorted(_POLICY_FILES_DIR.glob("*.cedar"))
if not _policy_files:
    raise RuntimeError(f"No .cedar policy files found in {_POLICY_FILES_DIR}")
_POLICY_SET = cedarpy.PolicySet.from_str(
    "\n\n".join(f.read_text() for f in _policy_files)
)
# Position in this list matches the auto-assigned positional policy ids
# cedarpy reports in diagnostics.reasons ("policy0", "policy1", ...), since
# policies were parsed from the same concatenation in the same order.
_POLICY_FILE_NAMES = [f.stem for f in _policy_files]


def _friendly_policy_id(raw_id: str) -> str:
    """Map cedarpy's positional 'policyN' id back to its source filename —
    purely for a more readable audit log; falls back to the raw id for
    anything that doesn't match the expected pattern (e.g. a future cedarpy
    version changes its id scheme)."""
    if raw_id.startswith("policy") and raw_id[len("policy"):].isdigit():
        index = int(raw_id[len("policy"):])
        if 0 <= index < len(_POLICY_FILE_NAMES):
            return _POLICY_FILE_NAMES[index]
    return raw_id


def authorize(principal: dict, action: dict, resource: dict, context: dict):
    """Evaluate a single request against the embedded Cedar engine.

    Returns (decision, determining_policy_ids): decision is "ALLOW" only for
    a genuine Decision.Allow; anything else (Decision.Deny, and the
    Decision.NoDecision that a malformed/unschema'd context produces) maps
    to "DENY" — a security gateway fails closed, it never treats an
    unexpected engine outcome as permission to proceed.
    """
    request = {"principal": principal, "action": action, "resource": resource, "context": context}
    result = cedarpy.is_authorized(request, _POLICY_SET, entities=[], schema=_SCHEMA)
    decision = "ALLOW" if result.decision == cedarpy.Decision.Allow else "DENY"
    determining_policy_ids = [_friendly_policy_id(pid) for pid in result.diagnostics.reasons]
    return decision, determining_policy_ids
