"""
Trend Trading HTTP API
======================
FastAPI application exposing Schwab market data, Satyland indicators,
and options analytics over a clean REST interface.

Start:
    uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
"""

import base64
import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import options, satyland, schwab

# If SCHWAB_TOKEN_B64 is set (Railway deployment), bootstrap the token file
# from the env var — but only if no token file exists yet (e.g. first deploy
# or volume is empty). On subsequent restarts the refreshed token on the
# persistent volume takes precedence, so we never overwrite it.
_token_b64 = os.getenv("SCHWAB_TOKEN_B64")
if _token_b64:
    _token_path = Path(os.getenv("SCHWAB_TOKEN_FILE", "/tmp/schwab_tokens.json"))
    if not _token_path.exists():
        try:
            _token_path.parent.mkdir(parents=True, exist_ok=True)
            # Remove any non-base64 characters (smart quotes, newlines, hidden chars)
            _clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', _token_b64)
            _token_path.write_bytes(base64.b64decode(_clean_b64))
        except OSError as e:
            import warnings
            warnings.warn(f"Could not write Schwab token to {_token_path}: {e}. "
                          "Check volume mount permissions.")

app = FastAPI(
    title="Trend Trading API",
    description="Schwab market data, Satyland indicators, and options analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS – restrict in production via ALLOWED_ORIGINS env var
_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in _origins_raw.split(",")] if _origins_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(schwab.router)
app.include_router(satyland.router)
app.include_router(options.router)


@app.get("/health", tags=["meta"])
async def health():
    """Health check – returns 200 when the API is up."""
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["meta"])
async def root():
    """API root – redirects to docs."""
    return {"message": "Trend Trading API", "docs": "/docs"}
