#!/usr/bin/env bash
# Full deploy for the Gateway & Policy slice.
#
# Order matters: the Cedar policy store must exist before the SAM stack,
# because the gateway Lambda needs its ID as an environment variable.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== 1/4: Cedar schema + policies -> Amazon Verified Permissions =="
python3 scripts/deploy_policies.py
POLICY_STORE_ID=$(cat .policy-store-id)
echo "Using policy store: ${POLICY_STORE_ID}"

echo "== 2/4: ensure the mode parameter exists (created once, never reset by redeploys) =="
bash scripts/ensure_mode_parameter.sh

echo "== 3/4: sam build =="
sam build

echo "== 4/4: sam deploy =="
sam deploy \
  --stack-name cellguard-gateway \
  --parameter-overrides "PolicyStoreId=${POLICY_STORE_ID}" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset

echo
echo "Deployed. Fetching the /invoke-tool URL:"
aws cloudformation describe-stacks \
  --stack-name cellguard-gateway \
  --query "Stacks[0].Outputs[?OutputKey=='InvokeToolUrl'].OutputValue" \
  --output text
