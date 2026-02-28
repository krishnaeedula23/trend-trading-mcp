import { cn } from "@/lib/utils"
import type { OptionsData, InstrumentOptionsData } from "@/hooks/use-options-data"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

function pctFmt(n: number | null | undefined): string {
  if (n == null) return "--"
  return `${n.toFixed(1)}%`
}

/** Color coding for IV rank/percentile: green <30, amber 30-60, red >60 */
function ivColor(value: number | null | undefined): string {
  if (value == null) return "text-muted-foreground"
  if (value < 30) return "text-emerald-400"
  if (value <= 60) return "text-amber-400"
  return "text-red-400"
}

function InstrumentRow({
  label,
  data,
}: {
  label: string
  data: InstrumentOptionsData
}) {
  const { straddle, iv } = data

  // Prefer Schwab ATM IV; fall back to VIX-based current_iv
  const ivValue =
    straddle?.atm_iv != null && straddle.atm_iv > 0
      ? straddle.atm_iv * 100 // decimal → percent
      : iv?.current_iv ?? null

  const rank = iv?.iv_rank ?? null
  const ptile = iv?.iv_percentile ?? null

  const em = straddle?.expected_move ?? null
  const emPct = straddle?.expected_move_pct ?? null
  const dte = straddle?.days_to_expiry ?? null

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
      <span className="text-sm font-medium w-10 shrink-0">{label}</span>

      {/* IV */}
      <div className="flex items-center gap-1 text-sm">
        <span className="text-muted-foreground text-xs">IV</span>
        <span className="font-mono">
          {ivValue != null ? pctFmt(ivValue) : "N/A"}
        </span>
      </div>

      {/* Rank */}
      <div className="flex items-center gap-1 text-sm">
        <span className="text-muted-foreground text-xs">Rank</span>
        <span className={cn("font-mono", ivColor(rank))}>
          {rank != null ? pctFmt(rank) : "N/A"}
        </span>
      </div>

      {/* Percentile */}
      <div className="flex items-center gap-1 text-sm">
        <span className="text-muted-foreground text-xs">Ptile</span>
        <span className={cn("font-mono", ivColor(ptile))}>
          {ptile != null ? pctFmt(ptile) : "N/A"}
        </span>
      </div>

      {/* Expected Move */}
      <div className="flex items-center gap-1 text-sm">
        <span className="text-muted-foreground text-xs">EM</span>
        <span className="font-mono">
          {em != null ? `\u00B1$${fmt(em)}` : "N/A"}
        </span>
        {emPct != null && (
          <span className="text-muted-foreground text-xs">
            ({pctFmt(emPct)})
          </span>
        )}
      </div>

      {/* Days to expiry */}
      {dte != null && (
        <span className="text-xs text-muted-foreground">
          {dte}d to exp
        </span>
      )}
    </div>
  )
}

export function OptionsDataSection({
  data,
  isLoading,
}: {
  data: OptionsData | null
  isLoading: boolean
}) {
  // Loading state — show skeleton
  if (isLoading) {
    return (
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Options Data
          </span>
          <div className="h-2 w-16 bg-muted animate-pulse rounded" />
        </div>
        <div className="h-5 w-3/4 bg-muted animate-pulse rounded" />
        <div className="h-5 w-3/4 bg-muted animate-pulse rounded" />
      </div>
    )
  }

  // No data at all — hide section
  if (!data) return null

  // Check if we have anything to show
  const hasAny =
    data.spy.straddle ||
    data.spy.iv ||
    data.spx.straddle ||
    data.spx.iv
  if (!hasAny) return null

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-2">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Options Data
      </span>

      {(data.spy.straddle || data.spy.iv) && (
        <InstrumentRow label="SPY" data={data.spy} />
      )}
      {(data.spx.straddle || data.spx.iv) && (
        <InstrumentRow label="SPX" data={data.spx} />
      )}
    </div>
  )
}
