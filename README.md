# Cell-Guard

A policy-enforcement gateway that sits between an AI agent and the tools
it's allowed to call. Every tool call is checked against Cedar authorization
policies in Amazon Verified Permissions before it executes — a deterministic
check the model cannot talk its way around, not a system-prompt suggestion.

Full context: [`Cell-Guard — Product Requirements Document.pdf`](./Cell-Guard%20%E2%80%94%20Product%20Requirements%20Document.pdf).

## Repo layout

Split along the one real seam in the architecture — the agent doesn't need
to know how the gateway enforces policy, and the gateway doesn't need to
know how the agent thinks. Both sides build against the same locked
`/invoke-tool` contract.

- **[`gateway-policy/`](./gateway-policy/)** — Person B: Cedar schema +
  policies in Amazon Verified Permissions, API Gateway + gateway Lambda, the
  3 tool Lambdas, the audit log. Fully testable with curl/Postman, no agent
  required. Start here: [`gateway-policy/README.md`](./gateway-policy/README.md).
- **`agent-frontend/`** — Person A: Bedrock tool-calling agent, chat UI, the
  injected-attack payload.

## Resource naming

`cellguard-gateway-*` (Person B) and `cellguard-agent-*` (Person A) — no
shared Lambda, no shared IAM role, no shared DynamoDB table between the two
sides. The only integration point is the `/invoke-tool` URL.
