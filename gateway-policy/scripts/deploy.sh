#!/usr/bin/env bash
# Full deploy for the Gateway & Policy slice.
#
# Order matters: the Cedar policy store must exist before the SAM stack,
# because the gateway Lambda needs its ID as an environment variable.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== 1/3: Cedar schema + policies -> Amazon Verified Permissions =="
python3 scripts/deploy_policies.py
POLICY_STORE_ID=$(cat .policy-store-id)
echo "Using policy store: ${POLICY_STORE_ID}"

echo "== 2/3: sam build =="
sam build

echo "== 3/3: sam deploy =="
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
