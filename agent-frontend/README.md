# Cell-Guard — Agent & Frontend (Person A)

This folder is Person A's slice: the Bedrock tool-calling agent, the chat
UI, and the injected-attack payload. Not built in this pass — this repo
currently only contains the **Gateway & Policy** slice (see
`../gateway-policy/`).

Build against the locked contract in `../gateway-policy/README.md` (`POST
/invoke-tool`). Per the PRD, start against a mock endpoint that always
returns `ALLOW`, then swap in the real gateway URL — that swap should be
the only line that changes.

The gateway is already deployed and verified end-to-end:
```
https://uh8orn4o0d.execute-api.us-east-1.amazonaws.com/prod/invoke-tool
```
Try it directly with `../gateway-policy/tests/curl-examples.sh` to see the
exact request/response shapes before wiring up the agent.
