"""Enforcement mode lookup — LOG_ONLY vs ENFORCE.

Backed by an SSM parameter so the mode can be flipped for the demo with a
single `aws ssm put-parameter` call and no Lambda redeploy (see
scripts/set-mode.sh). Fetched fresh on every request (no caching) so a flip
takes effect on the very next call, which matters when the mode toggle is
being demonstrated live.
"""

import os

import boto3

_ssm = boto3.client("ssm")
_PARAMETER_NAME = os.environ["MODE_PARAMETER_NAME"]
_VALID_MODES = {"LOG_ONLY", "ENFORCE"}
_DEFAULT_MODE = "LOG_ONLY"


def get_mode() -> str:
    try:
        response = _ssm.get_parameter(Name=_PARAMETER_NAME)
        value = response["Parameter"]["Value"].strip().upper()
    except _ssm.exceptions.ParameterNotFound:
        return _DEFAULT_MODE
    return value if value in _VALID_MODES else _DEFAULT_MODE
