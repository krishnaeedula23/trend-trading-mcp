"use client"
import type { SwingIdeaDetail } from "@/lib/types"

export function IdeaHeader({ idea }: { idea: SwingIdeaDetail }) {
  return (
    <header className="sticky top-0 z-10 bg-background/90 backdrop-blur border-b border-border py-3">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h1 className="text-2xl font-bold">{idea.ticker}</h1>
        <span className="text-sm rounded bg-secondary px-2 py-0.5">{idea.status}</span>
        <span className="text-sm text-muted-foreground">· {idea.cycle_stage}</span>
        <span className="text-sm text-muted-foreground">
          · confluence {idea.confluence_score}/10
        </span>
        <span className="text-xs text-muted-foreground ml-auto">
          detected {new Date(idea.detected_at).toLocaleDateString()}
        </span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground flex gap-4 flex-wrap">
        <span>stop ${idea.stop_price.toFixed(2)}</span>
        {idea.first_target != null && <span>target ${idea.first_target.toFixed(2)}</span>}
        {idea.next_earnings_date && <span>earnings {idea.next_earnings_date}</span>}
      </div>
    </header>
  )
}
