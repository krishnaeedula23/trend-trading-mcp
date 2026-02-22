#!/usr/bin/env python3
"""
One-time Schwab OAuth2 token generation.

Run this LOCALLY (not on Railway) once to create the token file.
After it succeeds, upload the token file to Railway as a secret file
or encode it as a base64 env var.

Usage:
    python scripts/schwab_auth.py

Prerequisites:
    1. Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env (or export them).
    2. Your Schwab app's callback URL must be registered at developer.schwab.com.
       For local use, register 'https://127.0.0.1' as the callback URL.
"""

import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import schwab.auth

API_KEY = os.environ.get("SCHWAB_CLIENT_ID", "")
APP_SECRET = os.environ.get("SCHWAB_CLIENT_SECRET", "")
CALLBACK_URL = os.environ.get("SCHWAB_REDIRECT_URI", "https://127.0.0.1")
TOKEN_FILE = os.environ.get("SCHWAB_TOKEN_FILE", "/tmp/schwab_tokens.json")


def main():
    if not API_KEY or not APP_SECRET:
        sys.exit(
            "ERROR: Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in your .env file.\n"
            "Get these from https://developer.schwab.com after creating an app."
        )

    print(f"\nToken will be saved to: {TOKEN_FILE}")
    print(f"Callback URL:           {CALLBACK_URL}\n")
    print("Make sure this callback URL is registered in your Schwab app settings.")
    print("=" * 60)

    # client_from_manual_flow prints the auth URL and prompts for the redirect URL
    client = schwab.auth.client_from_manual_flow(
        api_key=API_KEY,
        app_secret=APP_SECRET,
        callback_url=CALLBACK_URL,
        token_path=TOKEN_FILE,
    )

    # Quick smoke test
    resp = client.get_quote("AAPL")
    if resp.status_code == 200:
        data = resp.json()
        price = data.get("AAPL", {}).get("quote", {}).get("lastPrice", "N/A")
        print(f"\nSuccess! AAPL last price: ${price}")
        print(f"Token saved to: {TOKEN_FILE}")
        print("\nNext steps for Railway deployment:")
        print("  1. Encode the token:  base64 < " + TOKEN_FILE)
        print("  2. Add as Railway env var: SCHWAB_TOKEN_B64=<encoded value>")
        print("  3. In your app startup, decode it back to SCHWAB_TOKEN_FILE path")
    else:
        print(f"Warning: quote test returned {resp.status_code} - but token was saved.")


if __name__ == "__main__":
    main()
