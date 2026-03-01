import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { generateStrategyGuidance } from "@/lib/strategy-guidance"
import type { InstrumentPlan, VixSnapshot } from "@/lib/daily-plan-types"
import type { OptionsData } from "@/hooks/use-options-data"
import type { StrategyGuidance, EmAtrComparison, VixPremarketContext, StrategyScenario } from "@/lib/strategy-guidance"

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

function headlineColor(headline: string): string {
  if (headline.startsWith("Bullish")) return "text-emerald-400"
  if (headline.startsWith("Bearish")) return "text-red-400"
  return "text-amber-400"
}

function ScenarioCard({ scenario }: { scenario: StrategyScenario }) {
  const isChopzilla = scenario.label === "Inside Trigger Box"

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">
          {isChopzilla ? "⚠" : "▸"} {scenario.label}
        </span>
        {scenario.setupsToWatch.length > 0 && (
          <div className="flex gap-1">
            {scenario.setupsToWatch.map((s) => (
              <Badge
                key={s}
                variant="outline"
                className="text-[9px] px-1 text-muted-foreground border-border/40"
              >
                {s}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <p className={cn(
        "text-xs leading-relaxed",
        isChopzilla ? "text-amber-300/80" : "text-muted-foreground"
      )}>
        {scenario.description}
      </p>
      {scenario.actionItems.length > 0 && (
        <ul className="space-y-0.5">
          {scenario.actionItems.map((item, i) => (
            <li key={i} className="text-xs text-muted-foreground flex gap-1.5">
              <span className="text-muted-foreground/60 shrink-0">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function EmAtrSection({ emAtr }: { emAtr: EmAtrComparison }) {
  const deviationColor =
    emAtr.deviation === "aligned" ? "text-emerald-400"
      : emAtr.deviation === "wider" ? "text-amber-400"
        : "text-cyan-400"

  return (
    <div className="space-y-1">
      <span className="text-xs font-semibold text-muted-foreground">Expected Move vs ATR</span>
      <div className="text-xs text-muted-foreground">
        <span className="font-mono">
          EM ±${fmt(emAtr.emRange / 2)} (${fmt(emAtr.emLower)}-${fmt(emAtr.emUpper)})
        </span>
        <span className="mx-1.5">|</span>
        <span className="font-mono">ATR range ${fmt(emAtr.atrRange)}</span>
        <span className="mx-1.5">—</span>
        <span className={cn("font-medium", deviationColor)}>
          {emAtr.deviation.toUpperCase()}
        </span>
      </div>
      {emAtr.confluences.length > 0 && (
        <div className="space-y-0.5">
          {emAtr.confluences.map((c, i) => (
            <div key={i} className="text-xs text-cyan-300/80 flex gap-1">
              <span className="shrink-0">✦</span>
              <span>{c}</span>
            </div>
          ))}
        </div>
      )}
      <p className="text-[10px] text-muted-foreground/70">{emAtr.deviationNote}</p>
    </div>
  )
}

function VixPremktSection({ ctx }: { ctx: VixPremarketContext }) {
  const color =
    ctx.direction === "rising" ? "text-red-300"
      : ctx.direction === "falling" ? "text-emerald-300"
        : "text-muted-foreground"

  return (
    <div className={cn("text-xs", color)}>
      {ctx.note}
    </div>
  )
}

function InstrumentGuidance({
  plan,
  guidance,
}: {
  plan: InstrumentPlan
  guidance: StrategyGuidance
}) {
  return (
    <div className="space-y-3">
      {/* Headline */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold">{plan.displayName}</span>
          <span className={cn("text-sm font-medium", headlineColor(guidance.headline))}>
            — {guidance.headline}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">{guidance.gapReading}</p>
      </div>

      {/* VIX Premarket */}
      {guidance.vixPremkt && <VixPremktSection ctx={guidance.vixPremkt} />}

      {/* EM vs ATR */}
      {guidance.emAtr && <EmAtrSection emAtr={guidance.emAtr} />}

      <div className="h-px bg-border/20" />

      {/* Scenarios */}
      <div className="space-y-3">
        {guidance.scenarios.map((scenario, i) => (
          <ScenarioCard key={i} scenario={scenario} />
        ))}
      </div>

      <div className="h-px bg-border/20" />

      {/* ATR Room */}
      <div className={cn(
        "text-xs font-mono",
        guidance.atrNote.includes("green light") ? "text-emerald-400"
          : guidance.atrNote.includes("limited") ? "text-amber-400"
            : "text-red-400"
      )}>
        {guidance.atrNote}
      </div>
    </div>
  )
}

export function StrategySection({
  instruments,
  vix,
  optionsData,
}: {
  instruments: InstrumentPlan[]
  vix: VixSnapshot
  optionsData: OptionsData | null
}) {
  if (instruments.length === 0) return null

  // Map instrument ticker to options data
  function getOptionsForInstrument(ticker: string) {
    if (!optionsData) return null
    if (ticker === "SPY") return optionsData.spy
    if (ticker === "^GSPC") return optionsData.spx
    return null
  }

  const guidances = instruments.map((inst) => ({
    plan: inst,
    guidance: generateStrategyGuidance(inst, vix, getOptionsForInstrument(inst.ticker)),
  }))

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Today&apos;s Game Plan
        </span>
      </div>

      {guidances.map(({ plan, guidance }, i) => (
        <div key={plan.ticker}>
          {i > 0 && <div className="h-px bg-border/30 my-4" />}
          <InstrumentGuidance plan={plan} guidance={guidance} />
        </div>
      ))}

      {/* Entry Reminder — always shown */}
      <div className="rounded border border-blue-600/20 bg-blue-600/5 px-3 py-2">
        <p className="text-xs text-blue-300/80">
          {guidances[0]?.guidance.entryReminder ?? "Wait for BLUE or ORANGE candles. Never chase."}
        </p>
      </div>
    </div>
  )
}
