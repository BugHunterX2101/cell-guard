#!/usr/bin/env bash
# Full deploy for the Gateway & Policy slice.
#
# Authorization runs via an embedded Cedar engine (cedarpy) inside the
# gateway Lambda, not the managed Amazon Verified Permissions service — see
# src/gateway/common/engine.py's docstring for why. That means:
#   - No AWS policy-store step before the SAM stack; policies are staged
#     into the Lambda's own package and validated locally instead.
#   - `sam build` MUST run with --use-container: cedarpy ships a compiled
#     Rust extension, and it needs to be resolved for Lambda's Linux/x86_64
#     runtime, not whatever platform you're building on. Requires Docker
#     running locally.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== 1/4: stage + validate Cedar schema/policies (local, no AWS calls) =="
python3 scripts/prepare_policies.py

echo "== 2/4: ensure the mode parameter exists (created once, never reset by redeploys) =="
bash scripts/ensure_mode_parameter.sh

echo "== 3/4: sam build --use-container (needs Docker running) =="
sam build --use-container

echo "== 4/4: sam deploy =="
sam deploy \
  --stack-name cellguard-gateway \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset

echo
echo "Deployed. Fetching the /invoke-tool URL:"
aws cloudformation describe-stacks \
  --stack-name cellguard-gateway \
  --query "Stacks[0].Outputs[?OutputKey=='InvokeToolUrl'].OutputValue" \
  --output text
