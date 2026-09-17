# Cell-Guard — Gateway & Policy (Person B)

Owns: the Cedar schema + policies in Amazon Verified Permissions, the API
Gateway + gateway Lambda, the 3 tool Lambdas, and the audit log. Fully
testable with curl/Postman — the agent does not need to be running.

## Architecture

```
POST /invoke-tool  (API Gateway HTTP API)
        |
        v
  gateway Lambda  (cellguard-gateway-invoke-tool)
        |
        |-- verifiedpermissions:IsAuthorized  ---> Amazon Verified Permissions
        |                                          (Cedar schema + 5 policies)
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
grant the risky actions; Cedar's `IsAuthorized` decision is the gate.

## Why the policy store isn't a CloudFormation resource

`AWS::VerifiedPermissions::Policy` requires the Cedar statement inlined as a
template string, which would mean keeping the same policy text in two places
(the `.cedar` file and the template) and letting them drift. Instead,
`policies/schema.json` and `policies/policies/*.cedar` are the single source
of truth, and `scripts/deploy_policies.py` pushes them to AVP directly. This
is also much faster to iterate on — edit a `.cedar` file, rerun the script,
no stack update — which mattered given the timeline risk called out in the
PRD ("Cedar/AVP setup takes longer than expected").

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
  "result": {...},        // present only if decision is ALLOW
  "mode": "LOG_ONLY" | "ENFORCE",     // extra, non-breaking
  "policyDecision": "ALLOW" | "DENY" // extra: what Cedar actually decided,
                                      // even in LOG_ONLY where it isn't enforced
}
```

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

Prerequisites: AWS CLI configured with credentials (and a default region set), [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), and Python 3.12 available locally (`sam build` compiles against the local interpreter by default; add `--use-container` yourself, which then needs Docker, if your machine isn't on 3.12).

```bash
cd gateway-policy
bash scripts/deploy.sh
```

This runs, in order:
1. `scripts/deploy_policies.py` — creates/updates the AVP policy store, schema, and all 5 policies. Prints (and records in `.policy-store-id`) the policy store ID.
2. `scripts/ensure_mode_parameter.sh` — creates the `/cellguard/gateway/mode` SSM parameter defaulted to `LOG_ONLY`, but only if it doesn't already exist. It is deliberately *not* a CloudFormation resource: if it were, every `sam deploy` would reset its value back to the template's default, silently undoing a live flip made via `scripts/set-mode.sh` — e.g. redeploying to fix an unrelated bug right before recording the demo would quietly put you back in `LOG_ONLY`.
3. `sam build && sam deploy` — provisions the DynamoDB tables, 4 Lambdas, and the HTTP API, wiring the gateway Lambda's `POLICY_STORE_ID` env var to the ID from step 1 and `MODE_PARAMETER_NAME` to the parameter from step 2.

Output includes the `/invoke-tool` URL. Re-running `bash scripts/deploy.sh` any time afterward (to ship a code fix, say) is safe — it will not touch whatever mode you've flipped to.

Optional: seed a couple of sample customer records so `delete_customer_record` has something real to (attempt to) delete:
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
| `cellguard-gateway-invoke-tool` (gateway) | `verifiedpermissions:IsAuthorized` on this policy store only; `lambda:InvokeFunction` on the 3 tool functions only; `dynamodb:PutItem` on the audit table only; `ssm:GetParameter` on the mode parameter only |
| `cellguard-gateway-approve-expense` | `dynamodb:PutItem` on the app-data table only |
| `cellguard-gateway-delete-customer-record` | `dynamodb:DeleteItem` + `dynamodb:PutItem` on the app-data table only |
| `cellguard-gateway-send-wire-transfer` | `dynamodb:PutItem` on the app-data table only |

None of the tool Lambdas can be reached except by the gateway Lambda's
explicit `InvokeFunction` grant — there is no API Gateway route to them
directly.
