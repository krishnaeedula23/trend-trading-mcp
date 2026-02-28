import { cn } from "@/lib/utils"
import type { InstrumentPlan } from "@/lib/daily-plan-types"
import type { CalculateResponse } from "@/lib/types"

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "--"
  return n.toFixed(decimals)
}

const TF_ROWS: { key: keyof Pick<InstrumentPlan, "weekly" | "daily" | "hourly" | "fifteenMin">; label: string }[] = [
  { key: "weekly", label: "1W" },
  { key: "daily", label: "1D" },
  { key: "hourly", label: "1H" },
  { key: "fifteenMin", label: "15m" },
]

const EMA_COLS = ["ema8", "ema13", "ema21", "ema48", "ema200"] as const

export function MtfEmaGrid({ plan }: { plan: InstrumentPlan }) {
  const currentPrice = plan.daily.atr_levels.current_price

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border/30">
            <th className="py-1.5 pr-2 text-left font-medium text-muted-foreground">TF</th>
            {EMA_COLS.map((ema) => (
              <th
                key={ema}
                className="px-1 py-1.5 text-right font-medium text-muted-foreground"
              >
                {ema.replace("ema", "")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {TF_ROWS.map(({ key, label }) => {
            const data: CalculateResponse = key === "daily" ? plan.daily : plan[key]
            const ribbon = data.pivot_ribbon
            return (
              <tr key={key} className="border-b border-border/20">
                <td className="py-1.5 pr-2 font-mono font-medium text-muted-foreground">
                  {label}
                </td>
                {EMA_COLS.map((ema) => {
                  const val = ribbon[ema]
                  const isAbove = val != null && currentPrice > val
                  return (
                    <td
                      key={ema}
                      className={cn(
                        "px-1 py-1.5 text-right font-mono",
                        isAbove ? "text-emerald-400" : "text-red-400",
                      )}
                    >
                      {fmt(val)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
