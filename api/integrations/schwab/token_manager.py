"""
Schwab token path resolution.

schwab-py manages all token refresh logic internally. This module
just centralises the token file path so all parts of the app agree.
"""

import os
from pathlib import Path

TOKEN_PATH = Path(os.getenv("SCHWAB_TOKEN_FILE", "/tmp/schwab_tokens.json"))
_TMP_PATH = Path("/tmp/schwab_tokens.json")


def token_exists() -> bool:
    """Check configured path first, fall back to /tmp."""
    if TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size > 0:
        return True
    return _TMP_PATH.exists() and _TMP_PATH.stat().st_size > 0
