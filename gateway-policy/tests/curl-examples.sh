#!/usr/bin/env bash
# Exercises the /invoke-tool contract directly — no agent required.
# Set GATEWAY_URL to the InvokeToolUrl stack output before running.
#
# Usage:
#   export GATEWAY_URL="https://xxxx.execute-api.us-east-1.amazonaws.com/prod/invoke-tool"
#   bash tests/curl-examples.sh
set -euo pipefail

: "${GATEWAY_URL:?Set GATEWAY_URL to the deployed /invoke-tool endpoint first}"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "1. Happy path: approve_expense within threshold -> expect ALLOW"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "approve_expense",
  "params": { "amount": 120, "employee_id": "emp-42" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-001", "source": "chat" }
}' | python3 -m json.tool

hr "2. Attack via injected doc: approve_expense way over threshold -> expect DENY reason"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "approve_expense",
  "params": { "amount": 50000, "employee_id": "emp-42" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-002", "source": "injected_doc" }
}' | python3 -m json.tool

hr "3. Attack: delete_customer_record -> expect DENY unconditionally"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "delete_customer_record",
  "params": { "customer_id": "cust-1001" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-003", "source": "injected_doc" }
}' | python3 -m json.tool

hr "4. Happy path: send_wire_transfer within threshold -> expect ALLOW"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "send_wire_transfer",
  "params": { "amount": 250, "recipient": "vendor-acct-9" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-004", "source": "chat" }
}' | python3 -m json.tool

hr "5. Attack: send_wire_transfer over threshold -> expect DENY"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "send_wire_transfer",
  "params": { "amount": 25000, "recipient": "attacker-acct" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-005", "source": "injected_doc" }
}' | python3 -m json.tool

hr "6. Malformed request: unknown tool -> expect 400"
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "wipe_database",
  "params": {},
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-006", "source": "injected_doc" }
}'

hr "7. Edge case: negative approve_expense amount -> expect DENY (not an accidental ALLOW)"
curl -sS -X POST "$GATEWAY_URL" -H 'Content-Type: application/json' -d '{
  "tool": "approve_expense",
  "params": { "amount": -50, "employee_id": "emp-42" },
  "principal": { "user_id": "agent-session-1", "role": "agent" },
  "context": { "session_id": "sess-007", "source": "injected_doc" }
}' | python3 -m json.tool

echo
echo "Done. Compare results in LOG_ONLY vs ENFORCE mode with scripts/set-mode.sh,"
echo "and check cellguard-gateway-audit-log in DynamoDB for every attempt above."
