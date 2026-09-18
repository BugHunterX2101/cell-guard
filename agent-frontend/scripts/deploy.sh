#!/usr/bin/env bash
set -euo pipefail

sam build
if [[ "${USE_MOCK_GATEWAY:-true}" == "true" ]]; then
  sam deploy --guided --parameter-overrides UseMockGateway=true
else
  : "${GATEWAY_URL:?Set GATEWAY_URL to the gateway InvokeToolUrl from gateway-policy}"
  sam deploy --guided --parameter-overrides UseMockGateway=false GatewayUrl="$GATEWAY_URL"
fi
