"""Auth dependency + idempotency helper for Mac-Claude → Railway writes.

- `require_swing_token`: FastAPI dependency validating `Authorization: Bearer ...`
   against env `SWING_API_TOKEN`. Applied to POST endpoints only.
- `idempotent(sb, key, endpoint, handler)`: if `key` is given and seen within
   24h, returns the stored response; otherwise runs `handler` and stores it.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from fastapi import Header, HTTPException


def require_swing_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SWING_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="SWING_API_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization[len("Bearer ") :] != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def idempotent(sb, key: str | None, endpoint: str, handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Dedupe by Idempotency-Key for 24h. No-op if key is None.

    On hit: returns stored response.
    On miss: runs handler, stores response, returns it.
    Exceptions propagate; nothing is stored on error.
    """
    if key is None:
        return handler()

    existing = sb.table("swing_idempotency_keys").select("response_json").eq("key", key).execute().data or []
    if existing:
        return existing[0]["response_json"]

    result = handler()
    sb.table("swing_idempotency_keys").insert({
        "key": key,
        "endpoint": endpoint,
        "response_json": result,
    }).execute()
    return result
