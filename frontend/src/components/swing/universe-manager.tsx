"use client"

import { useState } from "react"
import { Trash2, Plus, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { UniverseUploadModal } from "./universe-upload-modal"
import { UniverseHistoryPanel } from "./universe-history-panel"
import { useSwingUniverse } from "@/hooks/use-swing-universe"

export function UniverseManager() {
  const { tickers, sourceSummary, activeCount, latestBatchAt, loading, error, refresh, addTicker, removeTicker, uploadCsv } = useSwingUniverse()
  const [newTicker, setNewTicker] = useState("")
  const [filter, setFilter] = useState("")
  const [showHistory, setShowHistory] = useState(false)

  const filtered = tickers.filter((t) => !filter || t.ticker.includes(filter.toUpperCase()))

  async function handleAdd() {
    const t = newTicker.trim().toUpperCase()
    if (!t) return
    try { await addTicker(t); setNewTicker(""); toast.success(`Added ${t}`) }
    catch (e) { toast.error(e instanceof Error ? e.message : "Add failed") }
  }

  async function handleRemove(ticker: string) {
    try { await removeTicker(ticker); toast.success(`Removed ${ticker}`) }
    catch (e) { toast.error(e instanceof Error ? e.message : "Remove failed") }
  }

  const freshness = latestBatchAt ? Math.floor((Date.now() - new Date(latestBatchAt).getTime()) / (1000 * 60 * 60 * 24)) : null
  const freshnessLabel = freshness === null ? "no uploads yet" : freshness <= 7 ? `✓ ${freshness}d ago` : `⚠ ${freshness}d ago (stale)`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium">Universe — {activeCount} active tickers</p>
          <p className="text-[10px] text-muted-foreground">Latest upload: {freshnessLabel}</p>
        </div>
        <div className="flex gap-1.5">
          <Button size="sm" variant="ghost" className="h-8" onClick={refresh} disabled={loading}>
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <UniverseUploadModal onUpload={uploadCsv} />
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setShowHistory((s) => !s)}>
            History
          </Button>
        </div>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {Object.entries(sourceSummary).map(([src, n]) => (
          <Badge key={src} variant="outline" className="text-[10px]">{src}: {n}</Badge>
        ))}
      </div>

      {showHistory && (
        <div className="rounded border border-border/40 p-3 bg-card/30">
          <UniverseHistoryPanel />
        </div>
      )}

      <div className="flex gap-2">
        <Input value={newTicker} onChange={(e) => setNewTicker(e.target.value)} placeholder="Add ticker..." className="h-8 text-xs w-32" onKeyDown={(e) => { if (e.key === "Enter") void handleAdd() }} />
        <Button size="sm" className="h-8" onClick={handleAdd} disabled={!newTicker.trim()}><Plus className="size-3.5" /></Button>
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter..." className="h-8 text-xs flex-1" />
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {loading && tickers.length === 0 ? (
        <div className="space-y-1"><Skeleton className="h-6" /><Skeleton className="h-6" /><Skeleton className="h-6" /></div>
      ) : (
        <div className="rounded border border-border/40 divide-y divide-border/30">
          {filtered.length === 0 ? (
            <p className="text-xs text-muted-foreground p-4 text-center">No tickers.</p>
          ) : filtered.slice(0, 500).map((t) => (
            <div key={t.ticker} className="flex items-center justify-between px-3 py-1.5 text-xs">
              <div className="flex gap-3 items-center">
                <span className="font-mono font-medium">{t.ticker}</span>
                <Badge variant="outline" className="text-[9px]">{t.source}</Badge>
              </div>
              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => handleRemove(t.ticker)}>
                <Trash2 className="size-3" />
              </Button>
            </div>
          ))}
          {filtered.length > 500 && <p className="text-[10px] text-muted-foreground p-2 text-center">+{filtered.length - 500} more (filter to narrow)</p>}
        </div>
      )}
    </div>
  )
}
