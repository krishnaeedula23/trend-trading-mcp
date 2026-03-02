# AI Chat Integration Design

**Date:** 2026-03-02
**Status:** Approved

## Goal

Add an AI chat experience to the frontend powered by Claude (via Vercel AI SDK) that can access all trading data through tool calling. Two surfaces: a slide-out drawer available on every page, and a dedicated `/chat` page for deeper sessions.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│ Frontend (Next.js on Vercel)                         │
│                                                      │
│  useChat() ──→ POST /api/chat ──→ streamText(claude) │
│    ↑                                  │              │
│    │ streaming                        │ tool calls   │
│    │ response                         ▼              │
│    │                          ┌──────────────┐       │
│    └──────────────────────────│ Tool Router  │       │
│                               └──────┬───────┘       │
└──────────────────────────────────────┼───────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                   │
                    ▼                  ▼                   ▼
           Railway API          MCP Server (SSE)     Supabase
           (indicators,        (research agents,    (cached scans,
            screeners,          multi-agent,         trade plans,
            quotes)             sentiment)           watchlists)
```

### Data flow

1. User types in chat → `useChat()` sends messages to `POST /api/chat`
2. Server route calls `streamText()` with Claude Sonnet 4 + tools
3. Claude decides which tools to call based on the question
4. Tool results flow back to Claude, which synthesizes a response
5. Response streams back to the user in real-time

## Tools

### Tier 1 — Railway API (fast, deterministic)

| Tool | Description | Endpoint |
|------|-------------|----------|
| `get_saty_indicators` | ATR levels, pivot ribbon, phase, green flag | `POST /api/satyland/calculate` |
| `run_vomy_scan` | VOMY screener (bullish/bearish/both, 1h/1d) | `POST /api/screener/vomy-scan` |
| `run_golden_gate_scan` | Golden Gate screener (day/multiday) | `POST /api/screener/golden-gate-scan` |
| `run_momentum_scan` | Momentum screener | `POST /api/screener/momentum-scan` |
| `get_trade_plan` | Today's daily trade plan | Internal Supabase read |
| `get_cached_scan` | Pre-cached screener results | `GET /api/screener/cached` |
| `get_watchlists` | User's watchlists and tickers | `GET /api/watchlists` |
| `get_options_data` | Options chain / flow data | `GET /api/options/...` |

### Tier 2 — MCP Server (AI agents, slower)

| Tool | Description | MCP Tool Name |
|------|-------------|---------------|
| `research_stock` | Deep web + news research | `research_comprehensive_research` |
| `analyze_sentiment` | Market sentiment analysis | `research_analyze_market_sentiment` |
| `technical_analysis` | Full TA report (RSI, MACD, S/R) | `technical_get_full_technical_analysis` |

## UI Components

### Slide-out Drawer

- Floating chat icon in bottom-right corner (available on every page)
- Opens a ~400px wide drawer from the right
- Maintains conversation across page navigation via React context
- Collapsed by default

### Dedicated `/chat` Page

- Full-width chat experience
- Shared conversation state with drawer (via context provider)
- Richer tool result rendering (full tables, inline charts)

### Shared Components

- `ChatMessage` — text + tool call results + thinking indicators
- `ChatInput` — text input, Shift+Enter for newlines
- `ToolResultCard` — compact inline cards for screener/indicator results
- `ChatProvider` — React context wrapping the app for shared state

## Dependencies

```
ai @ai-sdk/anthropic @ai-sdk/react zod
```

## Environment

```
ANTHROPIC_API_KEY=sk-ant-...   # Vercel dashboard
MCP_SERVER_URL=...             # Maverick MCP SSE endpoint (for Tier 2)
```

## Configuration

- **Model:** Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Max output tokens:** 4096
- **Max tool calls per turn:** 5
- **Conversation persistence:** sessionStorage (V1), Supabase later

## System Prompt

The system prompt will include:
- Saty indicator interpretation rules (what green flag means, phase meanings, ATR level significance)
- Trading strategy context (Maverick = what to trade, Saty = when to trade)
- Output formatting guidance (use tables for screener results, be concise)
- Tool selection guidance (use cached scans when available, prefer Tier 1 for speed)

## Error Handling

- Railway timeout → "Data temporarily unavailable" in tool result
- MCP connection failure → skip Tier 2 tools, note in response
- Claude API error → user-friendly error message in chat UI
- Tool execution error → include error in tool result, let Claude explain

## Future (not V1)

- Supabase `chat_messages` table for conversation history
- AI-enhanced daily trade plan (narrative from indicators)
- Remote MCP endpoint (expose server for Claude Desktop / Cursor)
- Voice input
- Chart rendering inline in chat
