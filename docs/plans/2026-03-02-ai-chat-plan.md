# AI Chat Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Claude-powered AI chat to the frontend (slide-out drawer + /chat page) that can query all trading data through tool calling.

**Architecture:** Vercel AI SDK (`ai` + `@ai-sdk/anthropic`) provides `useChat` on the client and `streamText` on the server. Claude Sonnet 4 is the model. Tools call Railway API (Tier 1) for indicators/screeners/quotes. A `ChatProvider` React context shares conversation state between the drawer and the dedicated page.

**Tech Stack:** `ai`, `@ai-sdk/anthropic`, `@ai-sdk/react`, `zod`, shadcn `Sheet` (right-side panel), `ScrollArea`, `Textarea`

**Design doc:** `docs/plans/2026-03-02-ai-chat-design.md`

---

### Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install AI SDK packages**

```bash
cd frontend && npm install ai @ai-sdk/anthropic @ai-sdk/react zod
```

**Step 2: Verify build still passes**

```bash
npm run build
```
Expected: Clean build, no errors.

**Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore: add Vercel AI SDK + Anthropic provider dependencies"
```

---

### Task 2: Define Chat Tools (Tier 1 — Railway)

**Files:**
- Create: `frontend/src/lib/ai/tools.ts`
- Create: `frontend/src/lib/ai/system-prompt.ts`

**Step 1: Create tool definitions**

Create `frontend/src/lib/ai/tools.ts` with Zod-schema'd tools that call `railwayFetch`:

```typescript
import { tool } from "ai"
import { z } from "zod"
import { railwayFetch } from "../railway"
import { createServerClient } from "../supabase/server"

export const tradingTools = {
  get_saty_indicators: tool({
    description:
      "Get Saty trading indicators (ATR levels, pivot ribbon, phase oscillator, green flag) for a ticker and timeframe. Use this to analyze a stock's current technical setup.",
    parameters: z.object({
      ticker: z.string().describe("Stock ticker symbol, e.g. AAPL"),
      timeframe: z
        .enum(["1h", "1d"])
        .default("1d")
        .describe("Timeframe for analysis"),
    }),
    execute: async ({ ticker, timeframe }) => {
      const res = await railwayFetch("/api/satyland/calculate", {
        ticker,
        timeframe,
      })
      return await res.json()
    },
  }),

  run_vomy_scan: tool({
    description:
      "Run the VOMY screener to find stocks with volume-momentum signals. Returns bullish/bearish/both hits across S&P 500 and NASDAQ 100.",
    parameters: z.object({
      timeframe: z
        .enum(["1h", "1d"])
        .default("1d")
        .describe("Scan timeframe"),
      signal_type: z
        .enum(["bullish", "bearish", "both"])
        .default("both")
        .describe("Signal direction"),
    }),
    execute: async ({ timeframe, signal_type }) => {
      const res = await railwayFetch("/api/screener/vomy-scan", {
        universes: ["sp500", "nasdaq100"],
        timeframe,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
      return await res.json()
    },
  }),

  run_golden_gate_scan: tool({
    description:
      "Run the Golden Gate screener to find stocks at golden gate entry levels. Supports day and multiday trading modes.",
    parameters: z.object({
      trading_mode: z
        .enum(["day", "multiday"])
        .default("day")
        .describe("Trading mode"),
      signal_type: z
        .enum(["golden_gate_up", "golden_gate_down", "golden_gate"])
        .default("golden_gate_up")
        .describe("Signal direction"),
    }),
    execute: async ({ trading_mode, signal_type }) => {
      const res = await railwayFetch("/api/screener/golden-gate-scan", {
        universes: ["sp500", "nasdaq100"],
        trading_mode,
        signal_type,
        min_price: 4.0,
        include_premarket: true,
      })
      return await res.json()
    },
  }),

  run_momentum_scan: tool({
    description:
      "Run the momentum screener to find stocks with strong momentum across all phases.",
    parameters: z.object({}),
    execute: async () => {
      const res = await railwayFetch("/api/screener/momentum-scan", {
        universes: ["sp500", "nasdaq100"],
        min_price: 4.0,
      })
      return await res.json()
    },
  }),

  get_trade_plan: tool({
    description:
      "Get today's daily trade plan with ATR levels, targets, and bias for key instruments (SPY, SPX, QQQ, NQ, ES).",
    parameters: z.object({}),
    execute: async () => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("daily_trade_plans")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(1)
        .single()
      return data
    },
  }),

  get_cached_scan: tool({
    description:
      "Get the latest pre-cached screener results from the premarket cron job. Faster than running a live scan.",
    parameters: z.object({
      scan_key: z
        .string()
        .describe(
          "Scan key, e.g. vomy:1d:both, golden_gate:day:golden_gate_up, momentum:default",
        ),
    }),
    execute: async ({ scan_key }) => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("cached_scans")
        .select("results, scanned_at")
        .eq("scan_key", scan_key)
        .single()
      return data
    },
  }),

  get_watchlists: tool({
    description: "Get the user's saved watchlists with ticker symbols.",
    parameters: z.object({}),
    execute: async () => {
      const supabase = createServerClient()
      const { data } = await supabase
        .from("watchlists")
        .select("*")
        .order("created_at", { ascending: false })
      return data ?? []
    },
  }),

  get_options_straddle: tool({
    description:
      "Get ATM straddle pricing and implied volatility for a ticker. Useful for gauging expected move.",
    parameters: z.object({
      ticker: z.string().describe("Stock ticker symbol"),
      strike_count: z
        .number()
        .default(10)
        .describe("Number of strikes around ATM"),
    }),
    execute: async ({ ticker, strike_count }) => {
      const res = await railwayFetch("/api/options/atm-straddle", {
        ticker,
        strike_count,
      })
      return await res.json()
    },
  }),
}
```

**Step 2: Create system prompt**

Create `frontend/src/lib/ai/system-prompt.ts`:

```typescript
export const TRADING_SYSTEM_PROMPT = `You are a trading assistant for the Saty Trading System. You help analyze stocks using the Saty indicator suite and screener tools.

## Saty Indicator Framework

- **ATR Levels**: Support/resistance levels derived from Average True Range. Key levels: PDC (previous day close), call trigger, put trigger, and Fibonacci-based price levels.
- **Pivot Ribbon**: 8 EMAs that show trend direction. States: bullish (EMAs aligned up), bearish (aligned down), chopzilla (tangled).
- **Phase Oscillator**: Momentum phase. Green = bullish momentum, Red = bearish momentum, Compression = coiling for a move.
- **Green Flag**: Confluence signal when ATR room is available, ribbon is trending, and phase supports direction.
- **VOMY**: Volume-Momentum scanner that finds stocks with volume surges confirming momentum.
- **Golden Gate**: Identifies stocks at key entry levels near golden gate zones.

## Trading Philosophy

- "Maverick MCP tells you WHAT to trade, Saty tells you WHEN to trade"
- Always check ATR room before entering — if ATR is exhausted (red status), the move may be done
- Green flag signals are highest-conviction entries
- Use the daily trade plan for key levels on indices (SPY, SPX, QQQ, NQ, ES)

## Response Guidelines

- Be concise and actionable — traders want quick answers
- When showing screener results, summarize the top 3-5 hits with key metrics
- Always mention ATR status and available room when discussing a setup
- Use tables for structured data (screener hits, levels)
- If cached scan data is available, prefer it over running a new scan for speed
- When asked about "setups today", check the cached premarket scans first
`
```

**Step 3: Verify build**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add src/lib/ai/
git commit -m "feat(chat): add trading tool definitions and system prompt"
```

---

### Task 3: Create Chat API Route

**Files:**
- Create: `frontend/src/app/api/chat/route.ts`

**Step 1: Create the streaming chat route**

```typescript
import { anthropic } from "@ai-sdk/anthropic"
import { streamText, type UIMessage } from "ai"
import { tradingTools } from "@/lib/ai/tools"
import { TRADING_SYSTEM_PROMPT } from "@/lib/ai/system-prompt"

export const maxDuration = 60

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json()

  const result = streamText({
    model: anthropic("claude-sonnet-4-20250514"),
    system: TRADING_SYSTEM_PROMPT,
    messages,
    tools: tradingTools,
    maxSteps: 5, // max tool call rounds per message
  })

  return result.toDataStreamResponse()
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build
```
Expected: Route appears as `ƒ /api/chat` in build output.

**Step 3: Commit**

```bash
git add src/app/api/chat/
git commit -m "feat(chat): add streaming chat API route with Claude + trading tools"
```

---

### Task 4: Create Chat UI Components

**Files:**
- Create: `frontend/src/components/chat/chat-message.tsx`
- Create: `frontend/src/components/chat/chat-input.tsx`
- Create: `frontend/src/components/chat/tool-result-card.tsx`
- Create: `frontend/src/components/chat/chat-panel.tsx`

**Step 1: Create ChatMessage component**

`frontend/src/components/chat/chat-message.tsx`:

```tsx
"use client"

import type { UIMessage } from "ai"
import { cn } from "@/lib/utils"
import { ToolResultCard } from "./tool-result-card"
import { Bot, User } from "lucide-react"

interface ChatMessageProps {
  message: UIMessage
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-3 py-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full border",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground",
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn("flex-1 space-y-2", isUser && "text-right")}>
        {message.parts.map((part, i) => {
          const key = `${message.id}-${i}`
          switch (part.type) {
            case "text":
              return (
                <div
                  key={key}
                  className="prose prose-sm prose-invert max-w-none"
                >
                  {part.text}
                </div>
              )
            case "tool-invocation":
              return (
                <ToolResultCard
                  key={key}
                  toolName={part.toolInvocation.toolName}
                  state={part.toolInvocation.state}
                  args={part.toolInvocation.args}
                  result={
                    part.toolInvocation.state === "result"
                      ? part.toolInvocation.result
                      : undefined
                  }
                />
              )
            default:
              return null
          }
        })}
      </div>
    </div>
  )
}
```

**Step 2: Create ToolResultCard component**

`frontend/src/components/chat/tool-result-card.tsx`:

```tsx
"use client"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Loader2, Search, BarChart3, Target, List } from "lucide-react"

const TOOL_META: Record<string, { label: string; icon: typeof Search }> = {
  get_saty_indicators: { label: "Saty Indicators", icon: BarChart3 },
  run_vomy_scan: { label: "VOMY Scan", icon: Search },
  run_golden_gate_scan: { label: "Golden Gate Scan", icon: Target },
  run_momentum_scan: { label: "Momentum Scan", icon: Search },
  get_trade_plan: { label: "Trade Plan", icon: Target },
  get_cached_scan: { label: "Cached Scan", icon: Search },
  get_watchlists: { label: "Watchlists", icon: List },
  get_options_straddle: { label: "Options Straddle", icon: BarChart3 },
}

interface ToolResultCardProps {
  toolName: string
  state: string
  args: Record<string, unknown>
  result?: unknown
}

export function ToolResultCard({
  toolName,
  state,
  args,
  result,
}: ToolResultCardProps) {
  const meta = TOOL_META[toolName] ?? { label: toolName, icon: Search }
  const Icon = meta.icon

  if (state !== "result") {
    return (
      <Card className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        <span>Calling {meta.label}...</span>
        {Object.keys(args).length > 0 && (
          <Badge variant="secondary" className="text-xs">
            {Object.entries(args)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")}
          </Badge>
        )}
      </Card>
    )
  }

  const data = result as Record<string, unknown> | null
  const totalHits =
    (data?.total_hits as number) ?? (data?.hits as unknown[])?.length

  return (
    <Card className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <span className="font-medium">{meta.label}</span>
        {totalHits !== undefined && (
          <Badge variant="secondary">{totalHits} hits</Badge>
        )}
      </div>
    </Card>
  )
}
```

**Step 3: Create ChatInput component**

`frontend/src/components/chat/chat-input.tsx`:

```tsx
"use client"

import { useRef, type KeyboardEvent } from "react"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { SendHorizonal } from "lucide-react"

interface ChatInputProps {
  input: string
  setInput: (value: string) => void
  onSubmit: () => void
  isLoading: boolean
}

export function ChatInput({
  input,
  setInput,
  onSubmit,
  isLoading,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !isLoading) {
        onSubmit()
      }
    }
  }

  return (
    <div className="flex items-end gap-2 border-t p-3">
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about setups, screeners, or indicators..."
        className="min-h-[40px] max-h-[120px] resize-none"
        rows={1}
      />
      <Button
        size="icon"
        onClick={onSubmit}
        disabled={!input.trim() || isLoading}
      >
        <SendHorizonal className="size-4" />
      </Button>
    </div>
  )
}
```

**Step 4: Create ChatPanel (assembles messages + input)**

`frontend/src/components/chat/chat-panel.tsx`:

```tsx
"use client"

import { useChat } from "@ai-sdk/react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import { useEffect, useRef } from "react"
import { Bot } from "lucide-react"

interface ChatPanelProps {
  className?: string
}

export function ChatPanel({ className }: ChatPanelProps) {
  const { messages, input, setInput, handleSubmit, status } = useChat({
    api: "/api/chat",
  })
  const scrollRef = useRef<HTMLDivElement>(null)
  const isLoading = status === "streaming" || status === "submitted"

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const onSubmit = () => {
    if (!input.trim()) return
    handleSubmit()
  }

  return (
    <div className={`flex flex-col ${className ?? ""}`}>
      <ScrollArea className="flex-1 px-3" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-muted-foreground">
            <Bot className="size-8" />
            <p className="text-sm">Ask me about your trading setups</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
      </ScrollArea>
      <ChatInput
        input={input}
        setInput={setInput}
        onSubmit={onSubmit}
        isLoading={isLoading}
      />
    </div>
  )
}
```

**Step 5: Verify build**

```bash
cd frontend && npm run build
```

**Step 6: Commit**

```bash
git add src/components/chat/
git commit -m "feat(chat): add ChatMessage, ChatInput, ToolResultCard, and ChatPanel components"
```

---

### Task 5: Create Chat Drawer (Slide-out Sheet)

**Files:**
- Create: `frontend/src/components/chat/chat-sheet.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create ChatSheet component**

`frontend/src/components/chat/chat-sheet.tsx`:

```tsx
"use client"

import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { MessageCircle } from "lucide-react"
import { ChatPanel } from "./chat-panel"

export function ChatSheet() {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          size="icon"
          className="fixed bottom-6 right-6 z-50 size-12 rounded-full shadow-lg"
        >
          <MessageCircle className="size-5" />
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-full flex-col p-0 sm:max-w-[420px]"
      >
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="text-sm font-medium">
            Trading Assistant
          </SheetTitle>
        </SheetHeader>
        <ChatPanel className="flex-1 overflow-hidden" />
      </SheetContent>
    </Sheet>
  )
}
```

**Step 2: Wire ChatSheet into layout.tsx**

Modify `frontend/src/app/layout.tsx` — add ChatSheet as a sibling to `<Toaster>`:

```tsx
// Add import at top:
import { ChatSheet } from "@/components/chat/chat-sheet"

// Add after <Toaster>:
<Toaster position="bottom-right" />
<ChatSheet />
```

**Step 3: Verify build**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add src/components/chat/chat-sheet.tsx src/app/layout.tsx
git commit -m "feat(chat): add slide-out chat drawer available on every page"
```

---

### Task 6: Create Dedicated /chat Page

**Files:**
- Create: `frontend/src/app/chat/page.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx` (add nav link)

**Step 1: Create /chat page**

`frontend/src/app/chat/page.tsx`:

```tsx
import { ChatPanel } from "@/components/chat/chat-panel"

export default function ChatPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="border-b px-4 py-3">
        <h1 className="text-lg font-semibold">Trading Assistant</h1>
        <p className="text-sm text-muted-foreground">
          Ask about setups, run screeners, or analyze tickers
        </p>
      </div>
      <ChatPanel className="flex-1 overflow-hidden" />
    </div>
  )
}
```

**Step 2: Add /chat to sidebar navigation**

Read `frontend/src/components/layout/sidebar.tsx` and add a nav item for `/chat`. Find the existing nav items array and add:

```tsx
{ href: "/chat", label: "Chat", icon: MessageCircle }
```

Import `MessageCircle` from `lucide-react`.

**Step 3: Verify build**

```bash
cd frontend && npm run build
```
Expected: `/chat` appears as `○ /chat` in build output.

**Step 4: Commit**

```bash
git add src/app/chat/ src/components/layout/sidebar.tsx
git commit -m "feat(chat): add dedicated /chat page with sidebar navigation"
```

---

### Task 7: Environment Setup + Manual Testing

**Files:**
- Modify: `frontend/.env.local` (add ANTHROPIC_API_KEY)

**Step 1: Add API key to local env**

Append to `frontend/.env.local`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

(Get key from https://console.anthropic.com/settings/keys)

**Step 2: Start dev server and test**

```bash
cd frontend && npm run dev
```

Open http://localhost:3000 and test:

1. Click the chat bubble in bottom-right → drawer opens
2. Type "What are today's best setups?" → Claude calls `get_cached_scan` tool → responds with summary
3. Type "Run a VOMY scan on 1h timeframe" → Claude calls `run_vomy_scan` → shows results
4. Type "Analyze AAPL" → Claude calls `get_saty_indicators` → interprets ATR levels
5. Navigate to `/chat` page → same experience in full-width layout

**Step 3: Add ANTHROPIC_API_KEY to Vercel**

```bash
cd frontend && npx vercel env add ANTHROPIC_API_KEY
```

Or add via Vercel dashboard → Project → Settings → Environment Variables.

**Step 4: Commit any tweaks**

```bash
git add -A && git commit -m "chore(chat): final tweaks from manual testing"
```

**Step 5: Push to main**

```bash
git push origin main
```

---

## Summary

| Task | What | New Files |
|------|------|-----------|
| 1 | Install deps | — |
| 2 | Tool definitions + system prompt | `lib/ai/tools.ts`, `lib/ai/system-prompt.ts` |
| 3 | Chat API route (streaming) | `app/api/chat/route.ts` |
| 4 | Chat UI components | `components/chat/chat-{message,input,panel}.tsx`, `tool-result-card.tsx` |
| 5 | Slide-out drawer | `components/chat/chat-sheet.tsx`, modify `layout.tsx` |
| 6 | /chat page + nav link | `app/chat/page.tsx`, modify `sidebar.tsx` |
| 7 | Env setup + manual test | `.env.local` |

**Total new files:** 8
**Modified files:** 3 (`package.json`, `layout.tsx`, `sidebar.tsx`)
