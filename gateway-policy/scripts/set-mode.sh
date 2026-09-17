#!/usr/bin/env bash
# Flip enforcement mode live, no redeploy — this is the switch the demo video
# is built around (LOG_ONLY -> ENFORCE, same attack, different outcome).
#
# Usage: scripts/set-mode.sh ENFORCE
#        scripts/set-mode.sh LOG_ONLY
set -euo pipefail

# See ensure_mode_parameter.sh for why: Git Bash/MSYS otherwise mangles the
# leading-slash parameter name into a Windows filesystem path.
export MSYS_NO_PATHCONV=1

MODE="${1:-}"
if [[ "${MODE}" != "LOG_ONLY" && "${MODE}" != "ENFORCE" ]]; then
  echo "Usage: $0 [LOG_ONLY|ENFORCE]" >&2
  exit 1
fi

aws ssm put-parameter \
  --name /cellguard/gateway/mode \
  --value "${MODE}" \
  --type String \
  --overwrite

echo "Mode set to ${MODE}. Takes effect on the next /invoke-tool call (no caching)."
