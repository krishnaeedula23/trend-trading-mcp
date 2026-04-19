"""Auth dependency + idempotency helper for Mac-Claude → Railway writes.

- `require_swing_token`: FastAPI dependency validating `Authorization: Bearer ...`
   against env `SWING_API_TOKEN`. Applied to POST endpoints only.
- `idempotent(sb, key, endpoint, handler)`: if `key` is given and seen within
   24h, returns the stored response; otherwise runs `handler` and stores it.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Callable

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


def require_swing_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SWING_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="SWING_API_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    # Constant-time compare — marginal risk on a 64-hex token over HTTPS,
    # but standard practice and a one-liner.
    if not hmac.compare_digest(authorization[len("Bearer ") :], expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def idempotent(sb, key: str | None, endpoint: str, handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Dedupe by Idempotency-Key for 24h. No-op if key is None.

    Semantics:
      - key=None → run handler unconditionally (no persistence).
      - cached hit → return stored response, don't run handler.
      - cached miss → run handler, store response, return result.
      - handler raises → propagate; nothing stored.
      - concurrent insert race → UniqueViolation on the 2nd INSERT is caught,
        the stored response from the first writer is returned instead of 500ing
        back to the caller. Both handlers still ran (not strictly serialized);
        this is acceptable for Mac-Claude's sequential-retry pattern. A stricter
        "claim-first, run-second" variant is deferred to Plan 4 if needed.
    """
    if key is None:
        return handler()

    existing = sb.table("swing_idempotency_keys").select("response_json").eq("key", key).execute().data or []
    if existing:
        return existing[0]["response_json"]

    result = handler()
    try:
        sb.table("swing_idempotency_keys").insert({
            "key": key,
            "endpoint": endpoint,
            "response_json": result,
        }).execute()
    except Exception as exc:  # UniqueViolation from concurrent writer
        logger.warning(
            "idempotency_keys insert failed for key=%s endpoint=%s (likely concurrent write): %s",
            key, endpoint, exc,
        )
        existing = sb.table("swing_idempotency_keys").select("response_json").eq("key", key).execute().data or []
        if existing:
            return existing[0]["response_json"]
        raise  # genuine failure — re-raise so caller sees 500 rather than silent corruption
    return result
