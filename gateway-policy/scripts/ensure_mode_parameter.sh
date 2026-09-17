#!/usr/bin/env bash
# Creates the LOG_ONLY/ENFORCE SSM parameter if it doesn't exist yet.
#
# Deliberately NOT a CloudFormation resource (see template.yaml's comment
# above the tool Lambdas): if it were, every `sam deploy` would reset its
# Value back to the template's default, silently undoing a live flip made
# via set-mode.sh between deploys — e.g. redeploying to fix an unrelated
# bug right before recording the demo would quietly put you back in
# LOG_ONLY. This script only ever creates it once; scripts/set-mode.sh is
# the only thing that changes its value after that.
set -euo pipefail

# On Windows/Git Bash, MSYS rewrites any argument that looks like a leading-
# slash Unix path (e.g. "/cellguard/...") into a Windows filesystem path
# before the aws CLI ever sees it — silently corrupting the parameter name.
# This disables that rewriting; it's a no-op on real Linux/macOS shells.
export MSYS_NO_PATHCONV=1

PARAM_NAME="/cellguard/gateway/mode"

if aws ssm get-parameter --name "${PARAM_NAME}" >/dev/null 2>&1; then
  CURRENT=$(aws ssm get-parameter --name "${PARAM_NAME}" --query 'Parameter.Value' --output text)
  echo "Mode parameter already exists (current value: ${CURRENT}) — leaving it as-is."
else
  aws ssm put-parameter --name "${PARAM_NAME}" --value "LOG_ONLY" --type String
  echo "Created ${PARAM_NAME} = LOG_ONLY."
fi
