import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { PivotRibbon, RibbonState, ConvictionArrow } from "@/lib/types"
import { ArrowUp, ArrowDown, Minus } from "lucide-react"

interface RibbonIndicatorProps {
  ribbon: PivotRibbon
}

const EMA_LABELS = ["EMA 8", "EMA 13", "EMA 21", "EMA 48", "EMA 200"] as const

function ribbonBarColors(state: RibbonState): string[] {
  switch (state) {
    case "bullish":
      return [
        "bg-emerald-400",
        "bg-emerald-500",
        "bg-emerald-600",
        "bg-emerald-700",
        "bg-emerald-800",
      ]
    case "bearish":
      return [
        "bg-red-400",
        "bg-red-500",
        "bg-red-600",
        "bg-red-700",
        "bg-red-800",
      ]
    case "chopzilla":
      return [
        "bg-zinc-400",
        "bg-zinc-500",
        "bg-zinc-500",
        "bg-zinc-600",
        "bg-zinc-700",
      ]
  }
}

function biasCircleColor(candle: string): string {
  switch (candle) {
    case "green":
      return "bg-emerald-500 shadow-emerald-500/50"
    case "blue":
      return "bg-blue-500 shadow-blue-500/50"
    case "orange":
      return "bg-orange-500 shadow-orange-500/50"
    case "red":
      return "bg-red-500 shadow-red-500/50"
    default:
      return "bg-zinc-500 shadow-zinc-500/50"
  }
}

function ConvictionArrowIcon({ arrow }: { arrow: ConvictionArrow }) {
  if (!arrow) return null

  if (arrow === "bullish_crossover") {
    return (
      <div className="flex items-center gap-1 text-emerald-400">
        <ArrowUp className="size-4" />
        <span className="text-[10px] font-medium">Bullish Cross</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 text-red-400">
      <ArrowDown className="size-4" />
      <span className="text-[10px] font-medium">Bearish Cross</span>
    </div>
  )
}

export function RibbonIndicator({ ribbon }: RibbonIndicatorProps) {
  const barColors = ribbonBarColors(ribbon.ribbon_state)
  const emaValues = [
    ribbon.ema8,
    ribbon.ema13,
    ribbon.ema21,
    ribbon.ema48,
    ribbon.ema200,
  ]

  return (
    <div className="space-y-3">
      {/* Bias candle + state header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              "size-4 rounded-full shadow-[0_0_8px]",
              biasCircleColor(ribbon.bias_candle)
            )}
          />
          <span className="text-sm font-medium capitalize">
            {ribbon.bias_candle} Candle
          </span>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            ribbon.ribbon_state === "bullish"
              ? "text-emerald-400 border-emerald-600/30"
              : ribbon.ribbon_state === "bearish"
                ? "text-red-400 border-red-600/30"
                : "text-zinc-400 border-zinc-600/30"
          )}
        >
          {ribbon.ribbon_state.toUpperCase()}
        </Badge>
      </div>

      {/* EMA ribbon bars */}
      <div className="space-y-1.5">
        {EMA_LABELS.map((label, i) => (
          <div key={label} className="flex items-center gap-3">
            <span className="w-14 text-right text-[11px] text-muted-foreground font-mono">
              {label}
            </span>
            <div className="flex-1 h-3 rounded-sm overflow-hidden bg-muted/30">
              <div
                className={cn("h-full rounded-sm transition-all", barColors[i])}
                style={{
                  width: `${60 + (4 - i) * 8}%`,
                }}
              />
            </div>
            <span className="w-16 text-right text-[11px] font-mono text-muted-foreground">
              {emaValues[i].toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {/* Indicators row */}
      <div className="flex items-center justify-between">
        {/* Compression */}
        {ribbon.in_compression ? (
          <div className="flex items-center gap-1.5">
            <Minus className="size-3.5 text-amber-400" />
            <span className="text-[10px] text-amber-400 font-medium">
              COMPRESSION
            </span>
          </div>
        ) : (
          <div />
        )}

        {/* Conviction arrow */}
        <ConvictionArrowIcon arrow={ribbon.conviction_arrow} />
      </div>
    </div>
  )
}
