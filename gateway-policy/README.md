# Cell-Guard — Gateway & Policy (Person B)

Owns: the Cedar schema + policies, the API Gateway + gateway Lambda, the 3
tool Lambdas, and the audit log. Fully testable with curl/Postman — the
agent does not need to be running.

**Architecture note:** the PRD calls for Cedar policy evaluated via Amazon
Verified Permissions. This deployment instead runs the same Cedar engine
**embedded** directly in the gateway Lambda, because Verified Permissions
is blocked account-wide on the AWS account this was built against — see
"Why embedded Cedar, not Amazon Verified Permissions" below before
assuming AVP is in play anywhere in this codebase.

## Architecture

```
POST /invoke-tool  (API Gateway HTTP API)
        |
        v
  gateway Lambda  (cellguard-gateway-invoke-tool)
        |
        |-- embedded Cedar engine (cedarpy, in-process)
        |     schema.json + 5 policies, staged into the Lambda's own
        |     package by scripts/prepare_policies.py, parsed once at
        |     cold start (common/engine.py)
        |
        |-- reads /cellguard/gateway/mode      ---> SSM Parameter Store
        |                                          (LOG_ONLY | ENFORCE)
        |
        |-- lambda:InvokeFunction (only if effective decision is ALLOW)
        |     |-- approve_expense
        |     |-- delete_customer_record
        |     |-- send_wire_transfer
        |          (each writes to cellguard-gateway-app-data)
        |
        `-- dynamodb:PutItem (every attempt, regardless of decision)
              -> cellguard-gateway-audit-log
```

No Lambda in this slice calls another tool Lambda directly, and no Lambda
holds IAM permission it doesn't use — see the `Policies:` block for each
function in `template.yaml`. The gateway Lambda's own AWS permissions do not
grant the risky actions; the embedded Cedar engine's decision is the gate,
evaluated in-process with no network call involved at all.

## Why embedded Cedar, not Amazon Verified Permissions

Every `verifiedpermissions:*` API call — `IsAuthorized`, `CreatePolicyStore`,
regardless of the specific action, IAM permissions granted, or AWS region
tried (`us-east-1`, `us-west-2`, `eu-west-1` all identical) — failed with:

```
AccessDeniedException: The AWS Access Key Id needs a subscription for the service
```

Unlike every other AWS service used here, that error never names a missing
IAM action (compare: `"not authorized to perform: dynamodb:ListTables
because no identity-based policy allows..."` for a normal denial). That
shape points to a block above the IAM-user level — most likely an AWS
Organizations Service Control Policy on the hackathon-provisioned sandbox
account (see https://www.wemakedevs.org/aws/first-commit), not a fixable
permissions gap. Verified Permissions isn't mentioned anywhere in that
hackathon's rules, while Cedar itself is explicitly listed as an endorsed
technology ("Cedar: authorization as policy" under the Build It track).

So: same authorization model, same Cedar policy language, same
`policies/schema.json` / `policies/policies/*.cedar` files (byte-for-byte
unchanged, validated against the real Cedar engine both before and after
this pivot) — just evaluated by the open-source Cedar engine directly
inside the gateway Lambda (via [`cedarpy`](https://pypi.org/project/cedarpy/),
the official Python bindings for the same Rust engine AVP itself runs on)
instead of calling out to the managed service. This also removes a network
hop from every tool call, which only helps the "keep the gateway check
fast" NFR, and gives friendlier audit-log entries (`cedarpy` reports which
`.cedar` file matched, e.g. `03-permit-approve-expense-within-threshold`,
rather than AVP's opaque `SPEXAMPLEabc123` policy IDs).

If Verified Permissions gets unblocked on your account later, swapping
back is a small, isolated change: reintroduce a boto3
`verifiedpermissions.is_authorized` call in `common/engine.py`'s
`authorize()` function (its signature — principal/action/resource/context
in, `(decision, determining_policy_ids)` out — doesn't need to change),
push the schema/policies to a real policy store, and drop the `cedarpy`
dependency. See git history for the pre-pivot AVP-based version of this
file if you want the exact original wiring back.

## The contract (locked — do not change without telling Person A)

```
POST /invoke-tool
Request: {
  "tool": "approve_expense" | "delete_customer_record" | "send_wire_transfer",
  "params": {...tool-specific},
  "principal": { "user_id": "string", "role": "agent" },
  "context": { "session_id": "string", "source": "chat" | "injected_doc" }
}
Response: {
  "decision": "ALLOW" | "DENY",
  "reason": "string",
  "result": {...},                    // present only if decision is ALLOW
  "mode": "LOG_ONLY" | "ENFORCE",      // extra, non-breaking
  "policyDecision": "ALLOW" | "DENY"   // extra: what Cedar actually decided,
                                       // even in LOG_ONLY where it isn't enforced
}
```

This contract is unchanged by the AVP-to-embedded-Cedar pivot — it's an
internal implementation swap inside the gateway Lambda. Person A's side
doesn't need to know or care which way authorization is evaluated.

`params` per tool:
- `approve_expense`: `{ "amount": number, "employee_id": "string" }`
- `delete_customer_record`: `{ "customer_id": "string" }`
- `send_wire_transfer`: `{ "amount": number, "recipient": "string" }`

## Policies (5 rules, in `policies/policies/`)

| Rule | Effect |
|---|---|
| `delete_customer_record` | Forbidden unconditionally |
| `approve_expense` amount > 500 | Forbidden |
| `approve_expense` amount in (0, 500] | Permitted |
| `send_wire_transfer` amount > 1000 | Forbidden |
| `send_wire_transfer` amount in (0, 1000] | Permitted |

Cedar semantics: an explicit `forbid` always wins over any `permit`, so
policy ordering doesn't matter and the thresholds can't be bypassed by a
crafted request that happens to also match a permit. The permits require a
strictly positive amount (not just "at or below the threshold") so a
negative amount doesn't slip through by accident — with no permit
matching, Cedar's default of implicit deny takes over.

`policies/schema.json` and `policies/policies/*.cedar` are the single
edited-by-humans source of truth. `scripts/prepare_policies.py` copies them
into `src/gateway/policies/` (a gitignored build artifact — the gateway
Lambda's package needs its own copy since SAM's `CodeUri` is a single
directory boundary) and validates them against the real Cedar engine before
every build, so a typo in a `.cedar` file fails fast locally instead of
surfacing as a Lambda cold-start crash after a successful `sam deploy`.

## LOG_ONLY vs ENFORCE

Mode lives in one SSM parameter (`/cellguard/gateway/mode`), read fresh on
every request — no caching, so a flip takes effect on the very next call.

- **ENFORCE**: the gateway's response mirrors Cedar's decision exactly. A
  DENY never reaches a tool Lambda.
- **LOG_ONLY**: Cedar is still evaluated and the real decision is written to
  the audit log and returned as `policyDecision`, but the tool always
  executes (`decision` in the response is always `ALLOW`). This is what lets
  the demo show the identical attack payload succeed in one mode and get
  blocked in the other.

Flip it live:
```bash
scripts/set-mode.sh ENFORCE
scripts/set-mode.sh LOG_ONLY
```

## Deploy

Prerequisites:
- AWS CLI configured with credentials and a default region set
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- **Docker, running locally.** This is now required (not optional): the
  gateway Lambda bundles [`cedarpy`](https://pypi.org/project/cedarpy/),
  which ships a compiled Rust extension. `sam build --use-container`
  builds it inside a Lambda-like Linux container so the extension matches
  Lambda's actual runtime platform, regardless of what OS you're
  developing on (this was built and deployed from Windows).

```bash
cd gateway-policy
bash scripts/deploy.sh
```

This runs, in order:
1. `scripts/prepare_policies.py` — stages `policies/` into the gateway
   Lambda's package and validates the schema + all 5 policies against the
   real Cedar engine. Pure local operation, no AWS calls.
2. `scripts/ensure_mode_parameter.sh` — creates the `/cellguard/gateway/mode`
   SSM parameter defaulted to `LOG_ONLY`, but only if it doesn't already
   exist. It is deliberately *not* a CloudFormation resource: if it were,
   every `sam deploy` would reset its value back to the template's default,
   silently undoing a live flip made via `scripts/set-mode.sh` — e.g.
   redeploying to fix an unrelated bug right before recording the demo
   would quietly put you back in `LOG_ONLY`.
3. `sam build --use-container && sam deploy` — provisions the DynamoDB
   tables, 4 Lambdas, and the HTTP API.

Output includes the `/invoke-tool` URL. Re-running `bash scripts/deploy.sh`
any time afterward (to ship a code fix, say) is safe — it will not touch
whatever mode you've flipped to.

Optional: seed a couple of sample customer records so `delete_customer_record`
has something real to (attempt to) delete:
```bash
python3 scripts/seed_data.py
```

## Test without the agent

```bash
export GATEWAY_URL="<InvokeToolUrl from the deploy output>"
bash tests/curl-examples.sh
```

Or import `tests/postman_collection.json` into Postman and set the
`gatewayUrl` collection variable. Both cover the same 7 cases: a happy-path
approval, an over-threshold expense attempt, an unconditional
customer-record deletion attempt, a happy-path and an over-threshold wire
transfer, a malformed request (unknown tool, expect HTTP 400), and a
negative-amount edge case (expect DENY, not an accidental ALLOW). Run the
same requests once with mode `LOG_ONLY` and once with `ENFORCE` to see the
contrast the demo is built around.

Every attempt — ALLOW or DENY — lands in `cellguard-gateway-audit-log`
(`aws dynamodb scan --table-name cellguard-gateway-audit-log`), with the
tool, params, principal, both the Cedar decision and the effective decision,
the mode at the time, a human-readable reason, and a timestamp.

## Resource naming

Everything here is prefixed `cellguard-gateway-*`: no shared Lambda, no
shared IAM role, no shared DynamoDB table with the agent/frontend side. The
only integration point with Person A's side is the `/invoke-tool` URL
itself.

## Least-privilege IAM, by function

| Function | Permissions |
|---|---|
| `cellguard-gateway-invoke-tool` (gateway) | `lambda:InvokeFunction` on the 3 tool functions only; `dynamodb:PutItem` on the audit table only; `ssm:GetParameter` on the mode parameter only |
| `cellguard-gateway-approve-expense` | `dynamodb:PutItem` on the app-data table only |
| `cellguard-gateway-delete-customer-record` | `dynamodb:DeleteItem` + `dynamodb:PutItem` on the app-data table only |
| `cellguard-gateway-send-wire-transfer` | `dynamodb:PutItem` on the app-data table only |

None of the tool Lambdas can be reached except by the gateway Lambda's
explicit `InvokeFunction` grant — there is no API Gateway route to them
directly. The gateway Lambda needs no AWS-service permission at all for the
authorization decision itself — it's evaluated in-process.
