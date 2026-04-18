"use client"

import { useEffect, useState } from "react"
import type { SwingIdeaListResponse } from "@/lib/types"

type HealthRegime = "bull" | "bear" | "neutral" | null

function regimeIcon(regime: string | null): string {
  if (!regime) return "⚪"
  const r = regime.toLowerCase()
  if (r.includes("bull") || r === "green") return "🟢"
  if (r.includes("bear") || r === "red") return "🔴"
  return "🟡"
}

function regimeLabel(regime: string | null): string {
  if (!regime) return "—"
  return regime.charAt(0).toUpperCase() + regime.slice(1).toLowerCase()
}

export function MarketHealthBar() {
  const [regime, setRegime] = useState<string | null>(null)
  const [breadth, setBreadth] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/swing/ideas?limit=1", { cache: "no-store" })
        if (!res.ok) return
        const data: SwingIdeaListResponse = await res.json()
        const first = data.ideas?.[0]
        if (first?.market_health) {
          const mh = first.market_health as Record<string, unknown>
          setRegime(typeof mh.regime === "string" ? mh.regime : null)
          setBreadth(typeof mh.breadth === "string" ? mh.breadth : null)
        }
      } catch {
        // silently ignore — bar just shows no data
      } finally {
        setLoaded(true)
      }
    })()
  }, [])

  if (!loaded) return null

  return (
    <div className="flex items-center gap-3 rounded border border-border/30 bg-card/30 px-3 py-2 text-xs">
      <span className="text-muted-foreground font-medium">Market Health</span>
      <span>
        {regimeIcon(regime)} Regime:{" "}
        <span className="font-medium">{regimeLabel(regime)}</span>
      </span>
      {breadth && (
        <span className="text-muted-foreground">
          Breadth: <span className="font-medium text-foreground">{breadth}</span>
        </span>
      )}
      {!regime && !breadth && (
        <span className="text-muted-foreground">No data</span>
      )}
    </div>
  )
}
