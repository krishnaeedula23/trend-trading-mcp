"use client"

import { useState, useMemo } from "react"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { WatchlistSection } from "@/components/watchlist/watchlist-section"
import { WatchlistEmptyState } from "@/components/watchlist/watchlist-card"
import { CreateWatchlistDialog } from "@/components/watchlist/create-watchlist-dialog"
import {
  useWatchlists,
  createWatchlist,
  updateWatchlist,
  deleteWatchlist,
} from "@/hooks/use-watchlists"
import { useBatchCalculate } from "@/hooks/use-batch-calculate"

export default function WatchlistsPage() {
  const { watchlists, isLoading: watchlistsLoading, refresh } = useWatchlists()
  const [createOpen, setCreateOpen] = useState(false)

  // Collect all unique tickers across all watchlists for a single batch call
  const allTickers = useMemo(() => {
    const set = new Set<string>()
    for (const wl of watchlists) {
      for (const t of wl.tickers) set.add(t)
    }
    return Array.from(set)
  }, [watchlists])

  const { results: batchResults, isLoading: batchLoading } =
    useBatchCalculate(allTickers)

  async function handleCreate(name: string, tickers: string[]) {
    try {
      await createWatchlist(name, tickers)
      toast.success("Watchlist created")
      refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create watchlist")
      throw err
    }
  }

  if (watchlistsLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
        </div>
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-32 rounded-lg border border-border/50 bg-card/50 animate-pulse"
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
        <Button
          size="sm"
          onClick={() => setCreateOpen(true)}
          className="gap-1.5"
        >
          <Plus className="size-4" />
          New Watchlist
        </Button>
      </div>

      {/* Sections or empty state */}
      {watchlists.length === 0 ? (
        <WatchlistEmptyState onCreate={() => setCreateOpen(true)} />
      ) : (
        <div className="space-y-3">
          {watchlists.map((wl) => (
            <WatchlistSection
              key={wl.id}
              watchlist={wl}
              batchResults={batchResults.filter((r) =>
                wl.tickers.includes(r.ticker)
              )}
              isLoading={batchLoading}
              onUpdate={updateWatchlist}
              onDelete={deleteWatchlist}
              onRefresh={refresh}
            />
          ))}
        </div>
      )}

      <CreateWatchlistDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={handleCreate}
      />
    </div>
  )
}
