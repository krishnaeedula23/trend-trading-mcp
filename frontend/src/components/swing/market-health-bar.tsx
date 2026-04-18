"use client"

import { useEffect, useState } from "react"
import type { SwingIdeaListResponse } from "@/lib/types"

function stageIcon(stage: string | null, greenLight: boolean | null): string {
  if (greenLight === true) return "🟢"
  if (greenLight === false && stage === "bear") return "🔴"
  if (greenLight === false) return "🟡"
  return "⚪"
}

function stageLabel(stage: string | null): string {
  if (!stage) return "—"
  return stage.charAt(0).toUpperCase() + stage.slice(1).toLowerCase()
}

export function MarketHealthBar() {
  const [stage, setStage] = useState<string | null>(null)
  const [greenLight, setGreenLight] = useState<boolean | null>(null)
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
          setStage(typeof mh.index_cycle_stage === "string" ? mh.index_cycle_stage : null)
          setGreenLight(typeof mh.green_light === "boolean" ? mh.green_light : null)
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
        {stageIcon(stage, greenLight)} QQQ:{" "}
        <span className="font-medium">{stageLabel(stage)}</span>
      </span>
      {greenLight !== null && (
        <span className="text-muted-foreground">
          {greenLight ? "Green light" : "No green light"}
        </span>
      )}
      {stage === null && greenLight === null && (
        <span className="text-muted-foreground">No data</span>
      )}
    </div>
  )
}
