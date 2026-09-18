# Cell-Guard — Agent & Frontend (Person A)

Person A's slice: a Bedrock Converse tool-calling agent, a static React chat UI,
four injection scenarios covering all three tools, a session audit trail, and a
development gateway so the whole demo runs with no AWS account attached.

## Contract and security boundary

The agent Lambda holds `bedrock:Converse` and nothing else. It has no permission
to invoke any tool Lambda. Every tool use is POSTed to the locked
`POST /invoke-tool` contract documented in `../gateway-policy/README.md`, and
`GatewayUrl` is the only value that changes at integration: start on the mock,
then swap in Person B's `InvokeToolUrl`.

The UI generates one `session_id` per page load and sends it with every request,
so all attempts from a demo run group together in the gateway's audit table.

## Design direction

A Swiss editorial system: white ground, hairline black rules, self-hosted
Archivo for text and JetBrains Mono for data, and one enforcement red (`#E4002B`)
reserved exclusively for policy signal — nothing decorative is ever red.

The interface turns on **three** verdict states, because two is not enough to
tell the story:

| State | Cedar | Tool ran | What it means |
|---|---|---|---|
| **Permitted** | ALLOW | yes | A legitimate call passed the gateway. |
| **Blocked** | DENY | no | ENFORCE stopped the call before the tool. |
| **Unenforced** | DENY | **yes** | LOG_ONLY recorded the denial and let it run. |

`Unenforced` is the whole point of LOG_ONLY and gets the loudest treatment on
screen — a red strip, and a red rail running straight through the gateway into a
filled tool node. `Blocked` gets the inverted strip and a severed rail.

Motion is concentrated in one authored moment: the `Agent → Gateway → Tool`
diagram on each verdict card, drawn with anime.js (`svg.createDrawable` for the
rails, a timeline for the gateway beat). The mode readout scrambles when the
gateway reports a different mode than last time, which is the flip the demo
video is built around. Entrances are CSS keyframes, so every resting state is
correct without JavaScript — a stalled frame loop leaves the page visible and
un-animated, never blank. All of it is disabled under `prefers-reduced-motion`.

## Run the UI with no AWS

`vite.config.ts` mounts a dev-only stand-in for the agent at `POST /chat`. It
routes a request to a tool and mirrors the published Cedar thresholds, so all
three verdict states are reachable locally. It is `apply: 'serve'` only and
never reaches a build.

```bash
cd agent-frontend
npm install
npm run dev                      # gateway reports LOG_ONLY
LOCAL_MODE=ENFORCE npm run dev   # gateway reports ENFORCE
```

To point the UI at a deployed agent instead, set `VITE_AGENT_API_URL` to the
`AgentApiUrl` stack output in `.env.local`.

## Deploy the agent

Already deployed and verified end-to-end against the real gateway:

```
https://hji9tqdwa3.execute-api.us-east-1.amazonaws.com/chat
```

```bash
curl -X POST https://hji9tqdwa3.execute-api.us-east-1.amazonaws.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Approve a $125 reimbursement for EMP-1048.","session_id":"try-it"}'
```

To redeploy or stand up your own copy:

```bash
cd agent-frontend
bash scripts/deploy.sh

# Integration: the one line that changes. Person B's gateway is already
# deployed and verified end-to-end (see ../gateway-policy/README.md) —
# this is its real InvokeToolUrl, usable as-is.
export USE_MOCK_GATEWAY=false
export GATEWAY_URL="https://uh8orn4o0d.execute-api.us-east-1.amazonaws.com/prod/invoke-tool"
bash scripts/deploy.sh
```

The default model is `amazon.nova-lite-v1:0`; change `BedrockModelId` only if
that model is unavailable in the chosen region. Host the `npm run build` output
(`dist/`) on Amplify Hosting or S3 + CloudFront.

**IAM gotcha found during deployment:** the Bedrock `Converse` API is
authorized by the `bedrock:InvokeModel` action, not a same-named `Converse`
action — granting only `bedrock:Converse` produces an `AccessDeniedException`
naming `bedrock:InvokeModel` as the missing permission. `template.yaml`
already grants the right action; this is here so nobody re-discovers it by
trial and error.

The in-stack mock reports `LOG_ONLY` by default and honours a `MockMode`
parameter, so the flip is rehearsable before Person B's stack exists. Once
integrated, Person B's SSM parameter governs the real mode and the mock is out
of the path entirely.

## Demo path

The gateway mode is on screen at all times, top right, so the flip is legible in
a recording.

1. **Routine Reimbursement** — $125 approval. Cedar ALLOW, tool runs,
   `Permitted`. This is the happy path at 0:20–0:50.
2. **Injected Over-Limit Approval** in LOG_ONLY — the note hides an instruction
   to approve $900. The card shows Cedar DENY against `amount=900` and the tool
   running anyway: `Unenforced`. This is "here's the gap" at 0:50–1:30.
3. Flip Person B's mode to ENFORCE (`gateway-policy/scripts/set-mode.sh
   ENFORCE`) and send **the exact same note**. Same `amount=900`, now `Blocked`,
   rail severed at the gateway. This is the centerpiece at 1:30–2:15.
4. **Injected Record Deletion** and **Injected Wire Transfer** put the other two
   tools through the same path, so the audit trail shows all three with their
   Cedar decision and whether they executed.
