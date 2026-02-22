"use client"

import { useState } from "react"
import Link from "next/link"
import { List, Plus, Settings } from "lucide-react"
import { toast } from "sonner"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { GradeBadge } from "@/components/ideas/grade-badge"
import { WatchlistManageDialog } from "@/components/watchlist/watchlist-manage-dialog"
import type { Watchlist } from "@/lib/types"
import type { BatchResultItem } from "@/lib/types"

interface WatchlistCardProps {
  watchlist: Watchlist
  batchResults?: BatchResultItem[]
  onUpdate: (id: string, data: { name?: string; tickers?: string[] }) => Promise<unknown>
  onDelete: (id: string) => Promise<unknown>
  onRefresh: () => void
}

export function WatchlistCard({
  watchlist,
  batchResults,
  onUpdate,
  onDelete,
  onRefresh,
}: WatchlistCardProps) {
  const [manageOpen, setManageOpen] = useState(false)

  const resultMap = new Map(
    batchResults?.map((r) => [r.ticker, r]) ?? []
  )

  return (
    <>
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <List className="size-4 text-muted-foreground" />
              <CardTitle className="text-sm">{watchlist.name}</CardTitle>
              <span className="text-xs text-muted-foreground">
                ({watchlist.tickers.length})
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setManageOpen(true)}
            >
              <Settings className="size-3.5" />
              <span className="sr-only">Manage watchlist</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {watchlist.tickers.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No tickers yet. Click the gear icon to add some.
            </p>
          ) : (
            <div className="space-y-1">
              {watchlist.tickers.map((ticker) => {
                const result = resultMap.get(ticker)
                return (
                  <Link
                    key={ticker}
                    href={`/analyze/${ticker}`}
                    className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted/50 transition-colors"
                  >
                    <span className="font-mono font-medium">{ticker}</span>
                    {result?.success && result.data?.green_flag && (
                      <GradeBadge
                        grade={result.data.green_flag.grade}
                        size="sm"
                      />
                    )}
                  </Link>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <WatchlistManageDialog
        watchlist={watchlist}
        open={manageOpen}
        onOpenChange={setManageOpen}
        onSave={async (data) => {
          try {
            await onUpdate(watchlist.id, data)
            toast.success("Watchlist updated")
            onRefresh()
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to update")
          }
        }}
        onDelete={async () => {
          try {
            await onDelete(watchlist.id)
            toast.success("Watchlist deleted")
            onRefresh()
            setManageOpen(false)
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed to delete")
          }
        }}
      />
    </>
  )
}

export function WatchlistEmptyState({
  onCreate,
}: {
  onCreate: () => void
}) {
  return (
    <Card className="bg-card/50 border-border/50">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-8">
        <List className="size-8 text-muted-foreground" />
        <div className="text-center space-y-1">
          <p className="text-sm font-medium">No watchlists yet</p>
          <p className="text-xs text-muted-foreground">
            Create a watchlist to track tickers
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onCreate} className="gap-1.5">
          <Plus className="size-3.5" />
          Create Watchlist
        </Button>
      </CardContent>
    </Card>
  )
}
