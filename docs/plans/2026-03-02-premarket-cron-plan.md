# Premarket Daily Cron — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Single daily cron at 6 AM PST runs all screeners + daily trade plan, caches in Supabase, frontend shows cached results on load.

**Architecture:** Vercel cron → Next.js API route → `railwayFetch` to Railway backend → upsert results into `cached_scans` Supabase table. Frontend hooks hydrate from cache on mount, user can still run manual live scans.

**Tech Stack:** Next.js 16 API routes, Supabase (postgres + RLS), Vercel cron, existing `railwayFetch` + `generateDailyPlan` utilities.

---

### Task 1: Create Supabase `cached_scans` Table

**Files:**
- No code files — run SQL via Supabase MCP tool

**Step 1: Create the table with RLS**

Run via `mcp__452c68d6-9f0d-46e2-84c8-e52e9c9d2a58__apply_migration`:

```sql
CREATE TABLE IF NOT EXISTS cached_scans (
  id         uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  scan_type  text NOT NULL,
  scan_key   text NOT NULL,
  results    jsonb NOT NULL,
  scanned_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(scan_key)
);

ALTER TABLE cached_scans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read" ON cached_scans
  FOR SELECT USING (true);

CREATE POLICY "service_role_all" ON cached_scans
  FOR ALL USING (true) WITH CHECK (true);
```

**Step 2: Verify table exists**

Run `execute_sql`: `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'cached_scans' ORDER BY ordinal_position;`

Expected: 5 columns (id, scan_type, scan_key, results, scanned_at).

**Step 3: Commit** — no code changes, just a note. Move on.

---

### Task 2: Scan Execution Library

**Files:**
- Create: `frontend/src/lib/run-screener-scans.ts`

**Step 1: Write the scan execution module**

This module defines the scan configs and the `runAllScans` function that calls Railway and upserts into Supabase.

```typescript
// frontend/src/lib/run-screener-scans.ts
// ---------------------------------------------------------------------------
// Premarket screener scan runner — called by the daily cron route.
// Runs each scan config against Railway, upserts results into cached_scans.
// ---------------------------------------------------------------------------

import { railwayFetch } from "./railway"
import { createServerClient } from "./supabase/server"

interface ScanConfig {
  scan_type: string
  scan_key: string
  path: string
  body: Record<string, unknown>
}

const SCAN_CONFIGS: ScanConfig[] = [
  {
    scan_type: "vomy",
    scan_key: "vomy:1h:both",
    path: "/api/screener/vomy-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      timeframe: "1h",
      signal_type: "both",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "vomy",
    scan_key: "vomy:1d:both",
    path: "/api/screener/vomy-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      timeframe: "1d",
      signal_type: "both",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "golden_gate",
    scan_key: "golden_gate:day:golden_gate",
    path: "/api/screener/golden-gate-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      trading_mode: "day",
      signal_type: "golden_gate",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "golden_gate",
    scan_key: "golden_gate:multiday:golden_gate",
    path: "/api/screener/golden-gate-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      trading_mode: "multiday",
      signal_type: "golden_gate",
      min_price: 4.0,
      include_premarket: true,
    },
  },
  {
    scan_type: "momentum",
    scan_key: "momentum:default",
    path: "/api/screener/momentum-scan",
    body: {
      universes: ["sp500", "nasdaq100"],
      min_price: 4.0,
    },
  },
]

export interface ScanResult {
  scan_key: string
  success: boolean
  total_hits?: number
  error?: string
  duration_ms: number
}

/**
 * Run all screener scans sequentially, upsert results to Supabase.
 * Returns a summary of each scan's outcome.
 */
export async function runAllScans(): Promise<ScanResult[]> {
  const supabase = createServerClient()
  const results: ScanResult[] = []

  for (const config of SCAN_CONFIGS) {
    const start = Date.now()
    try {
      const res = await railwayFetch(config.path, config.body)
      const data = await res.json()

      const { error } = await supabase.from("cached_scans").upsert(
        {
          scan_type: config.scan_type,
          scan_key: config.scan_key,
          results: data,
          scanned_at: new Date().toISOString(),
        },
        { onConflict: "scan_key" },
      )

      if (error) {
        results.push({
          scan_key: config.scan_key,
          success: false,
          error: `Supabase: ${error.message}`,
          duration_ms: Date.now() - start,
        })
      } else {
        results.push({
          scan_key: config.scan_key,
          success: true,
          total_hits: data.total_hits ?? data.hits?.length ?? 0,
          duration_ms: Date.now() - start,
        })
      }
    } catch (err) {
      results.push({
        scan_key: config.scan_key,
        success: false,
        error: String(err),
        duration_ms: Date.now() - start,
      })
    }
  }

  return results
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/lib/run-screener-scans.ts 2>&1 || npx next build 2>&1 | head -20`

Expected: No type errors.

**Step 3: Commit**

```bash
git add frontend/src/lib/run-screener-scans.ts
git commit -m "feat(cron): add screener scan execution library"
```

---

### Task 3: Cron Route

**Files:**
- Create: `frontend/src/app/api/cron/daily-screeners/route.ts`
- Delete: `frontend/src/app/api/cron/daily-plan/route.ts`
- Modify: `frontend/vercel.json`

**Step 1: Create the new cron route**

```typescript
// frontend/src/app/api/cron/daily-screeners/route.ts
import { NextRequest, NextResponse } from "next/server"
import { runAllScans } from "@/lib/run-screener-scans"
import { generateDailyPlan } from "@/lib/generate-daily-plan"

export const maxDuration = 300 // 5 min — scans are slow

export async function GET(request: NextRequest) {
  const authHeader = request.headers.get("authorization")
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const start = Date.now()

  // 1. Run all screener scans
  const scanResults = await runAllScans()

  // 2. Regenerate daily trade plan (premarket session)
  let tradePlanOk = false
  let tradePlanError: string | undefined
  try {
    await generateDailyPlan("premarket")
    tradePlanOk = true
  } catch (err) {
    tradePlanError = String(err)
  }

  const totalMs = Date.now() - start
  const succeeded = scanResults.filter((r) => r.success).length
  const failed = scanResults.filter((r) => !r.success).length

  return NextResponse.json({
    success: failed === 0 && tradePlanOk,
    scans: { succeeded, failed, details: scanResults },
    trade_plan: { success: tradePlanOk, error: tradePlanError },
    total_duration_ms: totalMs,
  })
}
```

**Step 2: Delete the old daily-plan cron route**

```bash
rm frontend/src/app/api/cron/daily-plan/route.ts
rmdir frontend/src/app/api/cron/daily-plan
```

**Step 3: Update vercel.json**

Replace contents of `frontend/vercel.json` with:

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-screeners",
      "schedule": "0 14 * * 1-5"
    }
  ]
}
```

**Step 4: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/app/api/cron/daily-screeners/route.ts frontend/vercel.json
git rm frontend/src/app/api/cron/daily-plan/route.ts
git commit -m "feat(cron): replace daily-plan with daily-screeners cron

Single cron at 14:00 UTC (6 AM PST) runs all screeners + trade plan.
Writes results to cached_scans Supabase table."
```

---

### Task 4: Cache Read Endpoint

**Files:**
- Create: `frontend/src/app/api/screener/cached/route.ts`

**Step 1: Write the cached scan reader**

```typescript
// frontend/src/app/api/screener/cached/route.ts
import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  const scanKey = request.nextUrl.searchParams.get("scan_key")
  if (!scanKey) {
    return NextResponse.json(
      { error: "Missing scan_key query parameter" },
      { status: 400 },
    )
  }

  const supabase = createServerClient()
  const { data, error } = await supabase
    .from("cached_scans")
    .select("results, scanned_at")
    .eq("scan_key", scanKey)
    .single()

  if (error || !data) {
    return NextResponse.json(
      { results: null, scanned_at: null },
      {
        headers: {
          "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
        },
      },
    )
  }

  return NextResponse.json(
    { results: data.results, scanned_at: data.scanned_at },
    {
      headers: {
        "Cache-Control": "s-maxage=60, stale-while-revalidate=300",
      },
    },
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds with new `/api/screener/cached` route listed.

**Step 3: Commit**

```bash
git add frontend/src/app/api/screener/cached/route.ts
git commit -m "feat(cron): add cached scan read endpoint"
```

---

### Task 5: Hook Cache Hydration — Shared Helper

**Files:**
- Create: `frontend/src/hooks/use-cached-scan.ts`

**Step 1: Write the shared cache-fetch hook**

```typescript
// frontend/src/hooks/use-cached-scan.ts
"use client"

import { useEffect, useRef, useState } from "react"

interface CachedScanData<T> {
  results: T | null
  scanned_at: string | null
}

/**
 * Fetch cached scan results from Supabase on mount.
 * Returns { cachedData, cachedAt, loadingCache }.
 */
export function useCachedScan<T>(scanKey: string | null) {
  const [cachedData, setCachedData] = useState<T | null>(null)
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const [loadingCache, setLoadingCache] = useState(false)
  const fetched = useRef(false)

  const fetchCache = async (key: string) => {
    setLoadingCache(true)
    try {
      const res = await fetch(`/api/screener/cached?scan_key=${encodeURIComponent(key)}`)
      if (!res.ok) return
      const data: CachedScanData<T> = await res.json()
      if (data.results) {
        setCachedData(data.results)
        setCachedAt(data.scanned_at)
      }
    } catch {
      // cache miss is fine — user can run manual scan
    } finally {
      setLoadingCache(false)
    }
  }

  useEffect(() => {
    if (fetched.current || !scanKey) return
    fetched.current = true
    void fetchCache(scanKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanKey])

  const refreshCache = () => {
    if (!scanKey) return
    fetched.current = false
    void fetchCache(scanKey)
  }

  return { cachedData, cachedAt, loadingCache, refreshCache }
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`

**Step 3: Commit**

```bash
git add frontend/src/hooks/use-cached-scan.ts
git commit -m "feat(cron): add useCachedScan shared hook"
```

---

### Task 6: Update Screener Hooks to Hydrate from Cache

**Files:**
- Modify: `frontend/src/hooks/use-vomy-scan.ts`
- Modify: `frontend/src/hooks/use-golden-gate-scan.ts`
- Modify: `frontend/src/hooks/use-momentum-scan.ts`

For each hook, the pattern is the same:
1. Import `useCachedScan`
2. Compute a `scanKey` from the current config defaults
3. Call `useCachedScan<ResponseType>(scanKey)`
4. On mount, if cache has data and no sessionStorage data, populate hits from cache
5. Expose `cachedAt`, `loadingCache`, `refreshCache` in the return object

**Step 1: Modify `use-vomy-scan.ts`**

Add import at top:
```typescript
import { useCachedScan } from "./use-cached-scan"
```

Add after the `hydrated` ref:
```typescript
const scanKey = `vomy:${config.timeframe}:${config.signal_type}`
const { cachedData, cachedAt, loadingCache, refreshCache } = useCachedScan<VomyScanResponse>(scanKey)
```

Update the hydration useEffect — after the existing sessionStorage hydration, add cache fallback:
```typescript
useEffect(() => {
  if (hydrated.current) return
  hydrated.current = true
  const saved = loadResponse()
  if (saved) {
    setHits(saved.hits)
    setResponse(saved)
  }
  setConfig(loadConfig())
}, [])

// Hydrate from Supabase cache if no sessionStorage data
useEffect(() => {
  if (response || scanning || !cachedData) return
  setHits(cachedData.hits)
  setResponse(cachedData)
}, [cachedData, response, scanning])
```

Update the return to include cache fields:
```typescript
return { hits, scanning, response, config, error, runScan, cancelScan, cachedAt, loadingCache, refreshCache }
```

Update `UseVomyScanReturn` interface to add:
```typescript
cachedAt: string | null
loadingCache: boolean
refreshCache: () => void
```

**Step 2: Modify `use-golden-gate-scan.ts`**

Same pattern. Import `useCachedScan`. Compute key:
```typescript
const scanKey = `golden_gate:${config.trading_mode}:${config.signal_type}`
const { cachedData, cachedAt, loadingCache, refreshCache } = useCachedScan<GoldenGateScanResponse>(scanKey)
```

Add cache hydration useEffect, update return type and return statement.

**Step 3: Modify `use-momentum-scan.ts`**

Same pattern. Import `useCachedScan`. Key is static:
```typescript
const scanKey = "momentum:default"
const { cachedData, cachedAt, loadingCache, refreshCache } = useCachedScan<MomentumScanResponse>(scanKey)
```

Add cache hydration useEffect, update return type and return statement.

**Step 4: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/hooks/use-vomy-scan.ts frontend/src/hooks/use-golden-gate-scan.ts frontend/src/hooks/use-momentum-scan.ts
git commit -m "feat(cron): hydrate screener hooks from Supabase cache on mount"
```

---

### Task 7: Cached Scan Banner Component

**Files:**
- Create: `frontend/src/components/screener/cached-scan-banner.tsx`

**Step 1: Write the banner component**

```tsx
// frontend/src/components/screener/cached-scan-banner.tsx
"use client"

import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface CachedScanBannerProps {
  cachedAt: string | null
  loading: boolean
  onRefresh: () => void
}

export function CachedScanBanner({ cachedAt, loading, onRefresh }: CachedScanBannerProps) {
  if (!cachedAt) return null

  const date = new Date(cachedAt)
  const formatted = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })

  return (
    <div className="flex items-center gap-2 rounded-md border border-border/50 bg-card/30 px-3 py-1.5 text-xs text-muted-foreground">
      <span>Premarket scan &middot; {formatted}</span>
      <Button
        size="sm"
        variant="ghost"
        className="h-5 gap-1 px-1.5 text-[10px]"
        onClick={onRefresh}
        disabled={loading}
      >
        <RefreshCw className={`size-3 ${loading ? "animate-spin" : ""}`} />
        Refresh
      </Button>
    </div>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`

**Step 3: Commit**

```bash
git add frontend/src/components/screener/cached-scan-banner.tsx
git commit -m "feat(cron): add CachedScanBanner component"
```

---

### Task 8: Integrate Banner into Screener Page

**Files:**
- Modify: `frontend/src/app/screener/page.tsx`

**Step 1: Add banner to each screener tab**

Add import:
```typescript
import { CachedScanBanner } from "@/components/screener/cached-scan-banner"
```

Add banner inside each `<TabsContent>`, before the Controls component:

For momentum tab:
```tsx
<CachedScanBanner cachedAt={momentum.cachedAt} loading={momentum.loadingCache} onRefresh={momentum.refreshCache} />
```

For golden-gate tab:
```tsx
<CachedScanBanner cachedAt={goldenGate.cachedAt} loading={goldenGate.loadingCache} onRefresh={goldenGate.refreshCache} />
```

For vomy tab:
```tsx
<CachedScanBanner cachedAt={vomy.cachedAt} loading={vomy.loadingCache} onRefresh={vomy.refreshCache} />
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/screener/page.tsx
git commit -m "feat(cron): show cached scan banners on screener page"
```

---

### Task 9: Final Build + Push

**Step 1: Full build check**

Run: `cd frontend && npm run build`

Expected: All routes compile, no type errors.

**Step 2: Push to main**

Run: `git push origin main`

**Step 3: Verify Vercel deployment picks up new cron**

Check Vercel dashboard → Project → Settings → Cron Jobs. Should show:
- `/api/cron/daily-screeners` at `0 14 * * 1-5`

**Step 4: Run the Supabase migration**

Use Supabase MCP or dashboard to create the `cached_scans` table (Task 1).

**Step 5: Test the cron manually**

```bash
curl -X GET https://your-vercel-domain.vercel.app/api/cron/daily-screeners \
  -H "Authorization: Bearer YOUR_CRON_SECRET"
```

Expected: JSON response with scan results summary.
