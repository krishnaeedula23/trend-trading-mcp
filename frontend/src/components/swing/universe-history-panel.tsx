"use client"

import { useEffect, useState } from "react"
import type { SwingUniverseHistoryEntry } from "@/lib/types"

export function UniverseHistoryPanel() {
  const [batches, setBatches] = useState<SwingUniverseHistoryEntry[]>([])
  useEffect(() => {
    void fetch("/api/swing/universe/history", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setBatches(d.batches || []))
      .catch(() => setBatches([]))
  }, [])
  if (batches.length === 0) return <p className="text-xs text-muted-foreground">No batches yet.</p>
  return (
    <div className="space-y-1.5">
      {batches.map((b) => (
        <div key={b.batch_id} className="flex justify-between text-xs border-b border-border/30 pb-1">
          <span className="font-mono">{new Date(b.uploaded_at).toLocaleString()}</span>
          <span>{b.source}</span>
          <span>{b.ticker_count} tickers</span>
        </div>
      ))}
    </div>
  )
}
