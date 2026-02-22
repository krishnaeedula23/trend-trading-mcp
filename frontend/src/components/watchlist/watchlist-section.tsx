"use client"

import { useState } from "react"
import Link from "next/link"
import { ChevronDown, ChevronRight, Settings } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { GradeBadge } from "@/components/ideas/grade-badge"
import { WatchlistManageDialog } from "@/components/watchlist/watchlist-manage-dialog"
import type { Watchlist, BatchResultItem } from "@/lib/types"
import { cn } from "@/lib/utils"

const biasColors: Record<string, string> = {
  green: "bg-emerald-500",
  blue: "bg-blue-500",
  orange: "bg-orange-500",
  red: "bg-red-500",
  gray: "bg-zinc-500",
}

const phaseColors: Record<string, string> = {
  green: "text-emerald-400 bg-emerald-500/10",
  red: "text-red-400 bg-red-500/10",
  compression: "text-yellow-400 bg-yellow-500/10",
}

interface WatchlistSectionProps {
  watchlist: Watchlist
  batchResults?: BatchResultItem[]
  isLoading: boolean
  onUpdate: (id: string, data: { name?: string; tickers?: string[] }) => Promise<unknown>
  onDelete: (id: string) => Promise<unknown>
  onRefresh: () => void
}

export function WatchlistSection({
  watchlist,
  batchResults,
  isLoading,
  onUpdate,
  onDelete,
  onRefresh,
}: WatchlistSectionProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)

  const resultMap = new Map(
    batchResults?.map((r) => [r.ticker, r]) ?? []
  )

  return (
    <>
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        {/* Section header */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex w-full items-center gap-2 px-4 py-3 hover:bg-muted/30 transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="size-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground shrink-0" />
          )}
          <span className="text-sm font-bold tracking-tight">{watchlist.name}</span>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {watchlist.tickers.length}
          </Badge>
          <div className="ml-auto" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setManageOpen(true)}
            >
              <Settings className="size-3.5" />
              <span className="sr-only">Manage watchlist</span>
            </Button>
          </div>
        </button>

        {/* Ticker table */}
        {!collapsed && (
          <div className="border-t border-border/30">
            {watchlist.tickers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">
                No tickers yet. Click the gear icon to add some.
              </p>
            ) : (
              <div className="divide-y divide-border/20">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_60px_40px_90px_80px] gap-2 px-4 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                  <span>Ticker</span>
                  <span className="text-center">Grade</span>
                  <span className="text-center">Bias</span>
                  <span className="text-center">Phase</span>
                  <span className="text-right">Price</span>
                </div>

                {/* Ticker rows */}
                {watchlist.tickers.map((ticker) => {
                  const result = resultMap.get(ticker)
                  const data = result?.success ? result.data : undefined

                  if (isLoading && !result) {
                    return (
                      <div
                        key={ticker}
                        className="grid grid-cols-[1fr_60px_40px_90px_80px] gap-2 items-center px-4 py-2"
                      >
                        <span className="text-sm font-mono font-medium">{ticker}</span>
                        <div className="flex justify-center"><Skeleton className="h-5 w-8" /></div>
                        <div className="flex justify-center"><Skeleton className="size-3 rounded-full" /></div>
                        <div className="flex justify-center"><Skeleton className="h-5 w-16" /></div>
                        <div className="flex justify-end"><Skeleton className="h-4 w-14" /></div>
                      </div>
                    )
                  }

                  const grade = data?.green_flag?.grade ?? null
                  const biasCandle = data?.pivot_ribbon?.bias_candle
                  const phase = data?.phase_oscillator?.phase
                  const price = data?.atr_levels?.current_price

                  return (
                    <Link
                      key={ticker}
                      href={`/analyze/${ticker}`}
                      className="grid grid-cols-[1fr_60px_40px_90px_80px] gap-2 items-center px-4 py-2 hover:bg-muted/30 transition-colors"
                    >
                      <span className="text-sm font-mono font-medium">{ticker}</span>

                      <div className="flex justify-center">
                        {grade ? (
                          <GradeBadge grade={grade} size="sm" />
                        ) : (
                          <span className="text-xs text-muted-foreground">--</span>
                        )}
                      </div>

                      <div className="flex justify-center">
                        {biasCandle ? (
                          <span
                            className={cn(
                              "size-3 rounded-full",
                              biasColors[biasCandle] ?? "bg-zinc-500"
                            )}
                            title={biasCandle}
                          />
                        ) : (
                          <span className="text-xs text-muted-foreground">--</span>
                        )}
                      </div>

                      <div className="flex justify-center">
                        {phase ? (
                          <Badge
                            variant="secondary"
                            className={cn(
                              "text-[10px] px-1.5 py-0 font-medium uppercase",
                              phaseColors[phase] ?? ""
                            )}
                          >
                            {phase}
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">--</span>
                        )}
                      </div>

                      <span className="text-sm font-mono text-right tabular-nums">
                        {price != null ? `$${price.toFixed(2)}` : "--"}
                      </span>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>

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
