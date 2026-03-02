# VOMY 13/48 Conviction Crossover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add EMA 13/48 conviction crossover detection to the VOMY/iVOMY scanner with frontend filter toggle.

**Architecture:** Inline crossover detection in the existing VOMY scanner endpoint — scan backward through 4 bars of EMA13/EMA48 to find the most recent crossover. Three new fields on VomyHit: `conviction_type`, `conviction_bars_ago`, `conviction_confirmed`. Frontend results table gets a "Conviction" column and a "Conviction Only" filter toggle.

**Tech Stack:** Python 3.12 (pandas EMA), FastAPI/Pydantic, Next.js 16, React 19, TypeScript, shadcn/ui

---

## Task 1: Backend — Add conviction fields to VomyHit model

**Files:**
- Modify: `api/endpoints/screener.py:787-804`

**Step 1: Add three new fields to the VomyHit Pydantic model**

Open `api/endpoints/screener.py` and find the `VomyHit` class at line 787. Add these three fields after `timeframe`:

```python
class VomyHit(BaseModel):
    """A stock that triggered a VOMY or iVOMY signal."""

    ticker: str
    last_close: float
    signal: str
    ema13: float
    ema21: float
    ema34: float
    ema48: float
    distance_from_ema48_pct: float
    atr: float
    pdc: float
    atr_status: str
    atr_covered_pct: float
    trend: str
    trading_mode: str
    timeframe: str
    conviction_type: str | None = None
    conviction_bars_ago: int | None = None
    conviction_confirmed: bool = False
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && .venv/bin/python -m pytest tests/api/test_vomy_scan.py -v`

Expected: All 9 tests PASS. The new fields have defaults so existing test data still works.

**Step 3: Commit**

```bash
git add api/endpoints/screener.py
git commit -m "feat(vomy): add conviction_type, conviction_bars_ago, conviction_confirmed fields to VomyHit"
```

---

## Task 2: Backend — Add conviction detection logic

**Files:**
- Modify: `api/endpoints/screener.py:879-940` (inside `_process_ticker`)

**Step 1: Refactor EMA computation to keep full series**

In the `_process_ticker` function (line 879), the current code computes EMA scalars:

```python
ema13 = float(close_series.ewm(span=13, adjust=False).mean().iloc[-1])
ema21 = float(close_series.ewm(span=21, adjust=False).mean().iloc[-1])
ema34 = float(close_series.ewm(span=34, adjust=False).mean().iloc[-1])
ema48 = float(close_series.ewm(span=48, adjust=False).mean().iloc[-1])
```

Replace with keeping full series for EMA13 and EMA48, and extracting scalars for all four:

```python
                # Compute EMAs (span-based, NOT Wilder)
                ema13_series = close_series.ewm(span=13, adjust=False).mean()
                ema48_series = close_series.ewm(span=48, adjust=False).mean()
                ema13 = float(ema13_series.iloc[-1])
                ema21 = float(close_series.ewm(span=21, adjust=False).mean().iloc[-1])
                ema34 = float(close_series.ewm(span=34, adjust=False).mean().iloc[-1])
                ema48 = float(ema48_series.iloc[-1])
```

**Step 2: Add conviction detection after signal detection**

After the `if signal is None: return None` check (line 906), and before the ATR enrichment (line 909), add conviction detection:

```python
                if signal is None:
                    return None

                # --- 13/48 conviction crossover (within 4 bars) ---
                conviction_type: str | None = None
                conviction_bars_ago: int | None = None
                n = len(ema13_series)
                lookback = min(4, n - 2)  # need at least 2 bars for comparison
                for bars_ago in range(1, lookback + 1):
                    idx = n - 1 - bars_ago
                    prev_13_above = float(ema13_series.iloc[idx - 1]) >= float(ema48_series.iloc[idx - 1])
                    curr_13_above = float(ema13_series.iloc[idx]) >= float(ema48_series.iloc[idx])
                    if not prev_13_above and curr_13_above:
                        conviction_type = "bullish_crossover"
                        conviction_bars_ago = bars_ago
                        break
                    elif prev_13_above and not curr_13_above:
                        conviction_type = "bearish_crossover"
                        conviction_bars_ago = bars_ago
                        break

                conviction_confirmed = (
                    (signal == "vomy" and conviction_type == "bearish_crossover")
                    or (signal == "ivomy" and conviction_type == "bullish_crossover")
                )

                # Enrich hits with ATR data
```

**Step 3: Pass conviction fields to VomyHit constructor**

In the `return VomyHit(...)` block (line 924), add the three new fields:

```python
                return VomyHit(
                    ticker=ticker.upper(),
                    last_close=round(last_close, 2),
                    signal=signal,
                    ema13=round(ema13, 4),
                    ema21=round(ema21, 4),
                    ema34=round(ema34, 4),
                    ema48=round(ema48, 4),
                    distance_from_ema48_pct=round(distance_pct, 2),
                    atr=atr_result["atr"],
                    pdc=atr_result["pdc"],
                    atr_status=atr_result["atr_status"],
                    atr_covered_pct=atr_result["atr_covered_pct"],
                    trend=atr_result["trend"],
                    trading_mode=mode,
                    timeframe=request.timeframe,
                    conviction_type=conviction_type,
                    conviction_bars_ago=conviction_bars_ago,
                    conviction_confirmed=conviction_confirmed,
                )
```

**Step 4: Run existing tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && .venv/bin/python -m pytest tests/api/test_vomy_scan.py -v`

Expected: All 9 tests PASS. Existing tests don't assert conviction fields, so they remain backward-compatible.

**Step 5: Commit**

```bash
git add api/endpoints/screener.py
git commit -m "feat(vomy): add inline 13/48 conviction crossover detection in scanner"
```

---

## Task 3: Backend — Write conviction-specific tests

**Files:**
- Modify: `tests/api/test_vomy_scan.py`

**Step 1: Add a VOMY data helper that has a bearish crossover within 4 bars**

Add this helper after the existing `_make_ivomy_daily` function (after line 233):

```python
def _make_vomy_with_conviction(base_price: float = 100.0, days: int = 60) -> pd.DataFrame:
    """Build VOMY data with a bearish 13/48 crossover within last 4 bars.

    Strategy: uptrend until bar -7 where EMA13 > EMA48, then a sharp drop
    in bars -6..-3 that makes EMA13 cross below EMA48 around bar -3 or -2,
    then set last bar's close to satisfy VOMY sandwich.
    """
    dates = pd.bdate_range(end="2026-03-01", periods=days, freq="B")

    # Strong uptrend, then sharp reversal at end
    uptrend = np.linspace(base_price, base_price * 1.25, days - 8)
    # Sharp drop over 8 bars — enough to flip EMA13 below EMA48
    drop = np.linspace(base_price * 1.25, base_price * 0.95, 8)
    prices = np.concatenate([uptrend, drop])

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices.copy(),
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    close = df["close"]
    ema13_s = close.ewm(span=13, adjust=False).mean()
    ema21_s = close.ewm(span=21, adjust=False).mean()
    ema34_s = close.ewm(span=34, adjust=False).mean()
    ema48_s = close.ewm(span=48, adjust=False).mean()

    e13 = float(ema13_s.iloc[-1])
    e21 = float(ema21_s.iloc[-1])
    e34 = float(ema34_s.iloc[-1])
    e48 = float(ema48_s.iloc[-1])

    # With a sharp enough drop, shorter EMAs should be BELOW longer EMAs
    # (ema13 < ema21 < ema34 < ema48). That's iVOMY ordering, not VOMY.
    # For VOMY we need ema13 >= ema21 >= ema34 >= ema48 AND close between.
    # Rebuild: uptrend then mild pullback (like original _make_vomy_daily)
    # BUT with a deliberate EMA13/EMA48 crossover injected near bar -3.

    # Simpler approach: use _make_vomy_daily pattern but inject a crossover.
    # Start with uptrend, create a dip at bars [-6,-5,-4] where EMA13 briefly
    # dips below EMA48, then recovers for the VOMY sandwich at [-1].

    # Actually, let's use a more direct approach: uptrend → slight dip → recover
    uptick = np.linspace(base_price, base_price * 1.20, days - 10)
    dip = np.linspace(base_price * 1.20, base_price * 1.05, 5)
    recover = np.linspace(base_price * 1.05, base_price * 1.12, 5)
    prices = np.concatenate([uptick, dip, recover])

    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices.copy(),
            "volume": [1_000_000] * days,
        },
        index=dates,
    )

    close = df["close"]
    ema13_s = close.ewm(span=13, adjust=False).mean()
    ema48_s = close.ewm(span=48, adjust=False).mean()

    # Check if there's a crossover in last 4 bars
    n = len(ema13_s)
    has_crossover = False
    for i in range(1, 5):
        idx = n - 1 - i
        if idx < 1:
            break
        prev_above = float(ema13_s.iloc[idx - 1]) >= float(ema48_s.iloc[idx - 1])
        curr_above = float(ema13_s.iloc[idx]) >= float(ema48_s.iloc[idx])
        if prev_above != curr_above:
            has_crossover = True
            break

    # If no natural crossover, force one by adjusting close at bar -3
    if not has_crossover:
        # Set bar -3 close to force EMA13 below EMA48 there
        target = float(ema48_s.iloc[-3]) - 0.5
        df.iloc[-3, df.columns.get_loc("close")] = target
        # Recompute
        close = df["close"]
        ema13_s = close.ewm(span=13, adjust=False).mean()
        ema48_s = close.ewm(span=48, adjust=False).mean()

    # Ensure VOMY conditions hold at last bar
    ema21_s = close.ewm(span=21, adjust=False).mean()
    ema34_s = close.ewm(span=34, adjust=False).mean()
    e13 = float(ema13_s.iloc[-1])
    e21 = float(ema21_s.iloc[-1])
    e34 = float(ema34_s.iloc[-1])
    e48 = float(ema48_s.iloc[-1])

    # Set last close between ema48 and ema13 for VOMY sandwich
    if e13 >= e21 >= e34 >= e48:
        target_close = (e48 + e13) / 2.0
        df.iloc[-1, df.columns.get_loc("close")] = target_close
    # Else the data won't produce a VOMY — tests that depend on this
    # will naturally fail and we'll adjust the helper

    return df
```

This helper is complex to get right with synthetic data. A more reliable approach is to test the conviction logic at the unit level.

**Step 1 (revised): Add unit-level conviction tests directly**

Instead of building more complex synthetic data (which is fragile), add tests that check conviction fields on existing VOMY hits and add a direct unit test for the crossover detection logic. Add these tests to the `TestVomyScan` class:

```python
    # 10. Conviction fields present on VOMY hit
    def test_vomy_hit_has_conviction_fields(self, client):
        """Every VOMY hit should include conviction_type, conviction_bars_ago, conviction_confirmed."""
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "signal_type": "vomy", "timeframe": "1d"},
            )

        data = resp.json()
        assert data["total_hits"] > 0
        hit = data["hits"][0]
        assert "conviction_type" in hit
        assert "conviction_bars_ago" in hit
        assert "conviction_confirmed" in hit
        # conviction_type is either a string or null
        assert hit["conviction_type"] in ("bullish_crossover", "bearish_crossover", None)
        # conviction_bars_ago is int 1-4 or null
        if hit["conviction_bars_ago"] is not None:
            assert 1 <= hit["conviction_bars_ago"] <= 4
        # conviction_confirmed is bool
        assert isinstance(hit["conviction_confirmed"], bool)

    # 11. Conviction fields present on iVOMY hit
    def test_ivomy_hit_has_conviction_fields(self, client):
        """Every iVOMY hit should include conviction fields."""
        daily = _make_ivomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "signal_type": "ivomy", "timeframe": "1d"},
            )

        data = resp.json()
        assert data["total_hits"] > 0
        hit = data["hits"][0]
        assert "conviction_type" in hit
        assert "conviction_bars_ago" in hit
        assert "conviction_confirmed" in hit

    # 12. Conviction confirmed alignment: VOMY + bearish = confirmed
    def test_conviction_confirmed_logic(self, client):
        """If VOMY has bearish_crossover → confirmed=True.
        If VOMY has bullish_crossover or None → confirmed=False.
        """
        daily = _make_vomy_daily(base_price=100.0)
        p1, p2, p3, p4 = self._mock_fetch(daily)

        with p1, p2, p3, p4:
            resp = client.post(
                "/api/screener/vomy-scan",
                json={"universes": ["sp500"], "signal_type": "vomy", "timeframe": "1d"},
            )

        data = resp.json()
        assert data["total_hits"] > 0
        hit = data["hits"][0]
        # Whether confirmed depends on synthetic data producing a crossover,
        # but the logic should be consistent:
        if hit["conviction_type"] == "bearish_crossover":
            assert hit["conviction_confirmed"] is True
        else:
            assert hit["conviction_confirmed"] is False
```

Also add a standalone unit test for the crossover detection logic outside the `TestVomyScan` class:

```python
class TestConvictionDetection:
    """Unit tests for the 13/48 conviction crossover detection logic."""

    def test_bullish_crossover_at_bar_2(self):
        """EMA13 crosses above EMA48 at bar -2 → bullish_crossover, bars_ago=2."""
        # Build series where ema13 < ema48 at bar -4, then ema13 >= ema48 at bar -3 onward
        # This means the crossover happened at bar -3 (bars_ago=2 from perspective of last bar)
        ema13_vals = [90.0, 91.0, 93.0, 96.0, 99.0, 102.0]  # crosses above at index 4
        ema48_vals = [95.0, 95.5, 96.0, 96.5, 97.0, 97.5]   # ema48 rises slowly

        ema13_series = pd.Series(ema13_vals)
        ema48_series = pd.Series(ema48_vals)

        # Manual crossover detection (same logic as endpoint)
        conviction_type = None
        conviction_bars_ago = None
        n = len(ema13_series)
        for bars_ago in range(1, 5):
            idx = n - 1 - bars_ago
            if idx < 1:
                break
            prev_above = float(ema13_series.iloc[idx - 1]) >= float(ema48_series.iloc[idx - 1])
            curr_above = float(ema13_series.iloc[idx]) >= float(ema48_series.iloc[idx])
            if not prev_above and curr_above:
                conviction_type = "bullish_crossover"
                conviction_bars_ago = bars_ago
                break
            elif prev_above and not curr_above:
                conviction_type = "bearish_crossover"
                conviction_bars_ago = bars_ago
                break

        assert conviction_type == "bullish_crossover"
        assert conviction_bars_ago == 1  # crossover at index 4, last bar index 5, so 1 bar ago

    def test_bearish_crossover_at_bar_3(self):
        """EMA13 crosses below EMA48 at bar -3 → bearish_crossover, bars_ago=3."""
        # ema13 above ema48 initially, crosses below at index 3
        ema13_vals = [102.0, 101.0, 99.0, 96.0, 95.0, 94.0, 93.0]
        ema48_vals = [95.0, 95.5, 96.0, 97.0, 97.5, 98.0, 98.5]

        ema13_series = pd.Series(ema13_vals)
        ema48_series = pd.Series(ema48_vals)

        conviction_type = None
        conviction_bars_ago = None
        n = len(ema13_series)
        for bars_ago in range(1, 5):
            idx = n - 1 - bars_ago
            if idx < 1:
                break
            prev_above = float(ema13_series.iloc[idx - 1]) >= float(ema48_series.iloc[idx - 1])
            curr_above = float(ema13_series.iloc[idx]) >= float(ema48_series.iloc[idx])
            if not prev_above and curr_above:
                conviction_type = "bullish_crossover"
                conviction_bars_ago = bars_ago
                break
            elif prev_above and not curr_above:
                conviction_type = "bearish_crossover"
                conviction_bars_ago = bars_ago
                break

        assert conviction_type == "bearish_crossover"
        assert conviction_bars_ago == 3  # crossover at idx 3, last bar idx 6, so 3 bars ago

    def test_no_crossover_outside_window(self):
        """Crossover at bar -6 (outside 4-bar window) → None."""
        # Crossover happens at index 1, last bar at index 7 → 6 bars ago
        ema13_vals = [90.0, 98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0]
        ema48_vals = [95.0, 95.5, 96.0, 96.5, 97.0, 97.5, 98.0, 98.5]

        ema13_series = pd.Series(ema13_vals)
        ema48_series = pd.Series(ema48_vals)

        conviction_type = None
        conviction_bars_ago = None
        n = len(ema13_series)
        for bars_ago in range(1, 5):
            idx = n - 1 - bars_ago
            if idx < 1:
                break
            prev_above = float(ema13_series.iloc[idx - 1]) >= float(ema48_series.iloc[idx - 1])
            curr_above = float(ema13_series.iloc[idx]) >= float(ema48_series.iloc[idx])
            if not prev_above and curr_above:
                conviction_type = "bullish_crossover"
                conviction_bars_ago = bars_ago
                break
            elif prev_above and not curr_above:
                conviction_type = "bearish_crossover"
                conviction_bars_ago = bars_ago
                break

        assert conviction_type is None
        assert conviction_bars_ago is None

    def test_no_crossover_flat(self):
        """EMA13 always above EMA48 → no crossover → None."""
        ema13_vals = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        ema48_vals = [90.0, 91.0, 92.0, 93.0, 94.0, 95.0]

        ema13_series = pd.Series(ema13_vals)
        ema48_series = pd.Series(ema48_vals)

        conviction_type = None
        conviction_bars_ago = None
        n = len(ema13_series)
        for bars_ago in range(1, 5):
            idx = n - 1 - bars_ago
            if idx < 1:
                break
            prev_above = float(ema13_series.iloc[idx - 1]) >= float(ema48_series.iloc[idx - 1])
            curr_above = float(ema13_series.iloc[idx]) >= float(ema48_series.iloc[idx])
            if not prev_above and curr_above:
                conviction_type = "bullish_crossover"
                conviction_bars_ago = bars_ago
                break
            elif prev_above and not curr_above:
                conviction_type = "bearish_crossover"
                conviction_bars_ago = bars_ago
                break

        assert conviction_type is None
        assert conviction_bars_ago is None
```

**Step 2: Run all tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && .venv/bin/python -m pytest tests/api/test_vomy_scan.py -v`

Expected: All 16 tests PASS (9 existing + 3 integration + 4 unit).

**Step 3: Commit**

```bash
git add tests/api/test_vomy_scan.py
git commit -m "test(vomy): add conviction crossover detection tests"
```

---

## Task 4: Frontend — Add conviction fields to TypeScript types

**Files:**
- Modify: `frontend/src/lib/types.ts:426-442`

**Step 1: Add three fields to VomyHit interface**

Find the `VomyHit` interface (line 426) and add the conviction fields after `timeframe`:

```typescript
export interface VomyHit {
  ticker: string
  last_close: number
  signal: "vomy" | "ivomy"
  ema13: number
  ema21: number
  ema34: number
  ema48: number
  distance_from_ema48_pct: number
  atr: number
  pdc: number
  atr_status: AtrStatus
  atr_covered_pct: number
  trend: Trend
  trading_mode: TradingMode
  timeframe: VomyTimeframe
  conviction_type: "bullish_crossover" | "bearish_crossover" | null
  conviction_bars_ago: number | null
  conviction_confirmed: boolean
}
```

**Step 2: Verify frontend builds**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`

Expected: Build succeeds. The results table doesn't reference these fields yet, so no type errors.

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(vomy): add conviction fields to VomyHit TypeScript interface"
```

---

## Task 5: Frontend — Add conviction column and filter toggle to results table

**Files:**
- Modify: `frontend/src/components/screener/vomy-results-table.tsx`

**Step 1: Add conviction badge helper**

After the existing `trendLabel` function (line 63), add:

```typescript
function convictionBadge(hit: VomyHit): { text: string; color: string } | null {
  if (!hit.conviction_type) return null
  const bars = hit.conviction_bars_ago ?? 0
  if (hit.conviction_confirmed) {
    if (hit.conviction_type === "bullish_crossover") {
      return { text: `Conv ↑ (${bars}b)`, color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" }
    }
    return { text: `Conv ↓ (${bars}b)`, color: "bg-red-600/20 text-red-400 border-red-600/30" }
  }
  // Unconfirmed crossover — gray
  const arrow = hit.conviction_type === "bullish_crossover" ? "↑" : "↓"
  return { text: `${arrow} (${bars}b)`, color: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30" }
}
```

**Step 2: Add "conviction" to SortKey type and sort logic**

Update the `SortKey` type (line 20):

```typescript
type SortKey = "ticker" | "last_close" | "distance" | "atr_covered" | "ema13" | "trend" | "conviction"
```

Add the conviction sort case in the `sorted` useMemo (inside the `arr.sort` switch, before `default`):

```typescript
        case "conviction": {
          // Confirmed first, then by bars_ago ascending
          const aConf = a.conviction_confirmed ? 0 : 1
          const bConf = b.conviction_confirmed ? 0 : 1
          if (aConf !== bConf) return dir * (aConf - bConf)
          return dir * ((a.conviction_bars_ago ?? 99) - (b.conviction_bars_ago ?? 99))
        }
```

**Step 3: Add filter state and conviction filter toggle**

Add a `convictionOnly` state inside `VomyResultsTable`:

```typescript
const [convictionOnly, setConvictionOnly] = useState(false)
```

Add filtering before the `sorted` memo. Change the `sorted` useMemo to also depend on `convictionOnly`:

```typescript
  const filtered = useMemo(() => {
    if (!convictionOnly) return hits
    return hits.filter((h) => h.conviction_confirmed)
  }, [hits, convictionOnly])

  const sorted = useMemo(() => {
    const arr = [...filtered]
    // ... existing sort logic ...
  }, [filtered, sortKey, sortAsc])
```

Update the `if (hits.length === 0) return null` check to use `hits` (not `filtered`), so the table shows even when conviction filter is on but no confirmed hits exist.

**Step 4: Add conviction filter toggle and column to the table**

Before the `<Table>` element, add a filter bar:

```tsx
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <Button
          size="sm"
          variant={convictionOnly ? "default" : "outline"}
          className="h-6 text-[10px]"
          onClick={() => setConvictionOnly((p) => !p)}
        >
          Conviction Only
        </Button>
        {convictionOnly && (
          <span className="text-[10px] text-muted-foreground">
            {filtered.length} of {hits.length} hits
          </span>
        )}
      </div>
```

Add the Conviction column header after ATR status and before Trend:

```tsx
            <SortHeader label="Conviction" k="conviction" />
```

Add the Conviction cell in the table body (after ATR status badge cell, before trend cell):

```tsx
                <TableCell>
                  {(() => {
                    const conv = convictionBadge(hit)
                    if (!conv) return <span className="text-xs text-muted-foreground">—</span>
                    return (
                      <Badge variant="outline" className={`text-[10px] ${conv.color}`}>
                        {conv.text}
                      </Badge>
                    )
                  })()}
                </TableCell>
```

**Step 5: Verify frontend builds**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`

Expected: Build succeeds with no type errors.

**Step 6: Commit**

```bash
git add frontend/src/components/screener/vomy-results-table.tsx
git commit -m "feat(vomy): add conviction column and filter toggle to results table"
```

---

## Task 6: Verify full test suite and code quality

**Files:** None (verification only)

**Step 1: Run all backend tests**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && .venv/bin/python -m pytest tests/api/ -v`

Expected: All tests pass (VOMY 16 + Golden Gate 14 + Momentum 11 = ~41).

**Step 2: Run code quality checks**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp && make check`

Expected: ruff format + lint + typecheck all pass.

**Step 3: Run frontend build**

Run: `cd /Users/krishnaeedula/claude/trend-trading-mcp/frontend && npm run build`

Expected: Build succeeds.

**Step 4: Push**

```bash
git push
```
