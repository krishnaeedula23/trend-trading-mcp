"use client"
import { useState } from "react"
import { useSwingModelBook } from "@/hooks/use-swing-model-book"
import { ModelBookCard } from "./model-book-card"

export function ModelBookGrid() {
  const [setup, setSetup] = useState<string>("")
  const [outcome, setOutcome] = useState<string>("")
  const { entries, isLoading } = useSwingModelBook({
    setup_kell: setup || undefined,
    outcome: outcome || undefined,
  })

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <select
          value={setup}
          onChange={e => setSetup(e.target.value)}
          className="rounded border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">All setups</option>
          <option value="wedge_pop">Wedge Pop</option>
          <option value="ema_crossback">EMA Crossback</option>
          <option value="base_n_break">Base-n-Break</option>
          <option value="reversal_extension">Reversal Extension</option>
          <option value="post_eps_flag">Post-EPS Flag</option>
        </select>
        <select
          value={outcome}
          onChange={e => setOutcome(e.target.value)}
          className="rounded border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">All outcomes</option>
          <option value="winner">Winner</option>
          <option value="loser">Loser</option>
          <option value="example">Example</option>
          <option value="missed">Missed</option>
        </select>
      </div>
      {isLoading ? (
        <div className="text-muted-foreground">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="text-muted-foreground">No entries yet.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {entries.map(e => <ModelBookCard key={e.id} entry={e} />)}
        </div>
      )}
    </div>
  )
}
