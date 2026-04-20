---
description: Manually add a historical exemplary setup to the model book. Ad-hoc.
trigger_phrases:
  - /swing-model-book-add
---

# /swing-model-book-add

See `_swing-shared.md` for env vars and bearer-token file location.

Args: free-form. Typical invocations:
- `/swing-model-book-add NVDA base_n_break 2024-03-15`
- `/swing-model-book-add` (no args → interactive)

## Steps

1. Parse args (ticker, setup, approximate date). If missing, ask user.
2. Pull historical chart via yfinance + a local plotter helper (or direct user to upload from TradingView). MVP path: ask user to paste TradingView screenshot URLs — skip autocapture.
3. Pull historical fundamentals via yfinance (rev growth trend at the time of the setup).
4. Ask user for:
   - Title (default: `<TICKER> <setup> <YYYY>`)
   - Outcome (winner/loser/example/missed)
   - R-multiple (if known)
   - Narrative (~100 words — what made it work/fail)
   - Key takeaways (bulleted)
   - Tags
   - Chart URLs (paste TradingView screenshot URLs, one per line). For each URL also ask:
     - Timeframe: one of daily | weekly | 60m | annotated (default: daily)
     - Source: one of tradingview-upload | user-markup (default: tradingview-upload)
5. `POST $RAILWAY_SWING_BASE/api/swing/model-book` with all fields:
   ```
   {
     "title": "...",
     "ticker": "NVDA",
     "setup_kell": "base_n_break",
     "outcome": "winner",
     "entry_date": "2024-03-15",
     "exit_date": "2024-05-02",
     "r_multiple": 3.2,
     "narrative": "...",
     "key_takeaways": ["...", "..."],
     "tags": ["semis", "AI"]
   }
   ```
6. If user pasted chart URLs: for each, `POST $RAILWAY_SWING_BASE/api/swing/charts` with:
   ```
   {
     "image_url": "<url>",
     "timeframe": "<daily|weekly|60m|annotated>",
     "source": "<tradingview-upload|user-markup>",
     "model_book_id": "<model_book_id from step 5>"
   }
   ```
7. Confirm: "✅ Added to Model Book — <link to /swing-ideas/model-book/<id>>".
