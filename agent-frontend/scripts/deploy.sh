#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

sam build
if [[ "${USE_MOCK_GATEWAY:-true}" == "true" ]]; then
  sam deploy --stack-name cellguard-agent --capabilities CAPABILITY_IAM --resolve-s3 \
    --no-confirm-changeset --parameter-overrides UseMockGateway=true
else
  : "${GATEWAY_URL:?Set GATEWAY_URL to the gateway InvokeToolUrl from gateway-policy}"
  sam deploy --stack-name cellguard-agent --capabilities CAPABILITY_IAM --resolve-s3 \
    --no-confirm-changeset --parameter-overrides UseMockGateway=false GatewayUrl="$GATEWAY_URL"
fi

echo
echo "Deployed. Fetching the chat API URL:"
aws cloudformation describe-stacks \
  --stack-name cellguard-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentApiUrl'].OutputValue" \
  --output text
