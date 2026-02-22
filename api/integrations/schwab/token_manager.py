"""
Schwab token path resolution.

schwab-py manages all token refresh logic internally. This module
just centralises the token file path so all parts of the app agree.
"""

import os
from pathlib import Path

TOKEN_PATH = Path(os.getenv("SCHWAB_TOKEN_FILE", "/tmp/schwab_tokens.json"))


def token_exists() -> bool:
    return TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size > 0
