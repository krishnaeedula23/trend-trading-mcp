"use client"

import { useRouter } from "next/navigation"
import { Eye, Zap, Target, ArrowRight } from "lucide-react"
import { toast } from "sonner"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TickerInput } from "@/components/analysis/ticker-input"
import { IdeaCard } from "@/components/ideas/idea-card"
import { IdeaCardSkeleton } from "@/components/skeletons/idea-card-skeleton"
import { StatCardSkeleton } from "@/components/skeletons/stat-card-skeleton"
import { useIdeas, updateIdea, deleteIdea } from "@/hooks/use-ideas"
import { useWatchlists, createWatchlist, updateWatchlist, deleteWatchlist } from "@/hooks/use-watchlists"
import { useBatchCalculate } from "@/hooks/use-batch-calculate"
import { WatchlistCard, WatchlistEmptyState } from "@/components/watchlist/watchlist-card"
import Link from "next/link"

function StatCard({
  label,
  count,
  icon: Icon,
  color,
}: {
  label: string
  count: number
  icon: React.ComponentType<{ className?: string }>
  color: string
}) {
  return (
    <Card className="bg-card/50 border-border/50">
      <CardContent className="flex items-center gap-4 p-4">
        <div
          className={`flex size-10 items-center justify-center rounded-lg ${color}`}
        >
          <Icon className="size-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold font-mono">{count}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const router = useRouter()

  const { ideas: activeIdeas, isLoading: loadingActive, refresh: refreshActive } = useIdeas("active")
  const { ideas: watchingIdeas, isLoading: loadingWatching } = useIdeas("watching")
  const { ideas: triggeredIdeas, isLoading: loadingTriggered } = useIdeas("triggered")
  const { watchlists, refresh: refreshWatchlists } = useWatchlists()

  // Collect all unique tickers from all watchlists for batch calculation
  const allWatchlistTickers = [...new Set(watchlists.flatMap((wl) => wl.tickers))]
  const { results: batchResults } = useBatchCalculate(allWatchlistTickers)

  const statsLoading = loadingActive || loadingWatching || loadingTriggered

  async function handleStatusChange(id: string, newStatus: string) {
    try {
      if (newStatus === "delete") {
        await deleteIdea(id)
        toast.success("Idea deleted")
      } else {
        await updateIdea(id, {
          status: newStatus as "watching" | "active" | "triggered" | "closed" | "expired",
        })
        toast.success(`Idea marked as ${newStatus}`)
      }
      refreshActive()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update idea")
    }
  }

  function handleAnalyze(ticker: string, timeframe: string, direction: string) {
    const params = new URLSearchParams({ tf: timeframe, dir: direction })
    router.push(`/analyze/${ticker}?${params.toString()}`)
  }

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of your trade ideas and quick analysis
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              label="Active Ideas"
              count={activeIdeas.length}
              icon={Zap}
              color="bg-blue-600"
            />
            <StatCard
              label="Watching"
              count={watchingIdeas.length}
              icon={Eye}
              color="bg-zinc-600"
            />
            <StatCard
              label="Triggered"
              count={triggeredIdeas.length}
              icon={Target}
              color="bg-emerald-600"
            />
          </>
        )}
      </div>

      {/* Watchlists */}
      <div className="space-y-4">
        <h2 className="text-base font-semibold">Watchlists</h2>
        {watchlists.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {watchlists.map((wl) => (
              <WatchlistCard
                key={wl.id}
                watchlist={wl}
                batchResults={batchResults.filter((r) =>
                  wl.tickers.includes(r.ticker)
                )}
                onUpdate={updateWatchlist}
                onDelete={deleteWatchlist}
                onRefresh={refreshWatchlists}
              />
            ))}
          </div>
        ) : (
          <WatchlistEmptyState
            onCreate={async () => {
              try {
                await createWatchlist("My Watchlist", [])
                toast.success("Watchlist created")
                refreshWatchlists()
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed to create watchlist")
              }
            }}
          />
        )}
      </div>

      {/* Active Ideas */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Active Ideas</h2>
          <Button asChild variant="ghost" size="sm" className="text-xs">
            <Link href="/ideas">
              View All
              <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        </div>

        {loadingActive ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <IdeaCardSkeleton key={i} />
            ))}
          </div>
        ) : activeIdeas.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {activeIdeas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>
        ) : (
          <Card className="bg-card/50 border-border/50">
            <CardContent className="flex flex-col items-center justify-center gap-2 py-10">
              <p className="text-sm text-muted-foreground">
                No active ideas yet
              </p>
              <p className="text-xs text-muted-foreground">
                Analyze a ticker below and save it as an idea
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Quick Analyze */}
      <div className="space-y-4">
        <h2 className="text-base font-semibold">Quick Analyze</h2>
        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-muted-foreground">
              Enter a ticker to run Saty analysis
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TickerInput onAnalyze={handleAnalyze} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
