import { cn } from "@/lib/utils"
import type { InstrumentPlan } from "@/lib/daily-plan-types"

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

export function DirectionalPlan({
  instruments,
}: {
  instruments: InstrumentPlan[]
}) {
  if (instruments.length === 0) return null

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/40">
            <th className="py-1.5 pr-2 text-left font-medium text-muted-foreground w-24" />
            <th className="px-2 py-1.5 text-left font-medium text-muted-foreground w-14" />
            <th className="px-2 py-1.5 text-right font-medium text-muted-foreground">T1</th>
            <th className="px-2 py-1.5 text-right font-medium text-muted-foreground">T2</th>
            <th className="px-2 py-1.5 text-right font-medium text-muted-foreground">T3</th>
          </tr>
        </thead>
        <tbody>
          {/* Upside */}
          {instruments.map((inst, i) => {
            const targets = inst.targets.upside
            return (
              <tr
                key={`up-${inst.ticker}`}
                className={cn(
                  "border-b",
                  i === instruments.length - 1
                    ? "border-border/40"
                    : "border-border/20",
                )}
              >
                {i === 0 && (
                  <td
                    rowSpan={instruments.length}
                    className="py-1.5 pr-2 align-middle font-semibold text-emerald-400"
                  >
                    Upside
                  </td>
                )}
                <td className="px-2 py-1.5 font-medium">{inst.displayName}</td>
                {[0, 1, 2].map((ti) => {
                  const t = targets[ti]
                  if (!t) {
                    return (
                      <td key={ti} className="px-2 py-1.5 text-right font-mono text-muted-foreground">
                        --
                      </td>
                    )
                  }
                  return (
                    <td
                      key={ti}
                      className={cn(
                        "px-2 py-1.5 text-right font-mono",
                        t.confluenceCount > 1
                          ? "text-emerald-300 font-semibold"
                          : "text-foreground",
                      )}
                      title={
                        t.confluences.length > 0
                          ? `${t.label} (${t.source}) + ${t.confluences.join(", ")}`
                          : `${t.label} (${t.source})`
                      }
                    >
                      {fmt(t.price)}
                      {t.confluenceCount > 1 && (
                        <span className="ml-1 text-[10px] text-emerald-500">
                          x{t.confluenceCount}
                        </span>
                      )}
                    </td>
                  )
                })}
              </tr>
            )
          })}

          {/* Downside */}
          {instruments.map((inst, i) => {
            const targets = inst.targets.downside
            return (
              <tr
                key={`dn-${inst.ticker}`}
                className={cn(
                  i < instruments.length - 1 && "border-b border-border/20",
                )}
              >
                {i === 0 && (
                  <td
                    rowSpan={instruments.length}
                    className="py-1.5 pr-2 align-middle font-semibold text-red-400"
                  >
                    Downside
                  </td>
                )}
                <td className="px-2 py-1.5 font-medium">{inst.displayName}</td>
                {[0, 1, 2].map((ti) => {
                  const t = targets[ti]
                  if (!t) {
                    return (
                      <td key={ti} className="px-2 py-1.5 text-right font-mono text-muted-foreground">
                        --
                      </td>
                    )
                  }
                  return (
                    <td
                      key={ti}
                      className={cn(
                        "px-2 py-1.5 text-right font-mono",
                        t.confluenceCount > 1
                          ? "text-red-300 font-semibold"
                          : "text-foreground",
                      )}
                      title={
                        t.confluences.length > 0
                          ? `${t.label} (${t.source}) + ${t.confluences.join(", ")}`
                          : `${t.label} (${t.source})`
                      }
                    >
                      {fmt(t.price)}
                      {t.confluenceCount > 1 && (
                        <span className="ml-1 text-[10px] text-red-500">
                          x{t.confluenceCount}
                        </span>
                      )}
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
