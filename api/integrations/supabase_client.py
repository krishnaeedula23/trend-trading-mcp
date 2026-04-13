"""Supabase client initialization for trading companion data persistence.

Uses the service role key (bypasses RLS) because this client is used
exclusively by the FastAPI server on Railway — never exposed to the frontend.
"""

import os
from functools import lru_cache

from supabase import create_client, Client


@lru_cache
def get_supabase() -> Client:
    """Get or create the Supabase client singleton.

    Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. "
            "Get these from your Supabase project settings."
        )
    return create_client(url, key)
