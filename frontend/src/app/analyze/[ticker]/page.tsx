"use client"

import React, { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Save, CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { TickerInput } from "@/components/analysis/ticker-input"
import { IndicatorPanel } from "@/components/analysis/indicator-panel"
import { GreenFlagChecklist } from "@/components/analysis/green-flag-checklist"
import { GradeBadge } from "@/components/ideas/grade-badge"
import { IndicatorPanelSkeleton } from "@/components/skeletons/indicator-panel-skeleton"
import { ErrorDisplay } from "@/components/ui/error-display"
import { useTradePlan } from "@/hooks/use-trade-plan"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError, userMessage } from "@/lib/errors"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function AnalyzeTickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>
}) {
  const { ticker } = React.use(params)
  const router = useRouter()
  const searchParams = useSearchParams()

  const timeframe = searchParams.get("tf") ?? "1d"
  const direction = searchParams.get("dir") ?? "bullish"

  const { data, error, isLoading, refresh } = useTradePlan(ticker, timeframe, direction)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  function handleAnalyze(
    newTicker: string,
    newTimeframe: string,
    newDirection: string
  ) {
    setSaved(false)
    const params = new URLSearchParams({
      tf: newTimeframe,
      dir: newDirection,
    })
    router.push(`/analyze/${newTicker}?${params.toString()}`)
  }

  async function handleSaveIdea() {
    if (!data) return
    setSaving(true)
    try {
      await createIdea({
        ticker: data.ticker,
        direction: data.direction as "bullish" | "bearish",
        timeframe: data.timeframe,
        status: "watching",
        grade: data.green_flag.grade,
        ribbon_state: data.pivot_ribbon.ribbon_state,
        bias_candle: data.pivot_ribbon.bias_candle,
        phase: data.phase_oscillator.phase,
        atr_status: data.atr_levels.atr_status,
        score: data.green_flag.score,
        current_price: data.atr_levels.current_price,
        call_trigger: data.atr_levels.call_trigger,
        put_trigger: data.atr_levels.put_trigger,
        source: "analyze",
        indicator_snapshot: data as unknown as Record<string, unknown>,
      })
      setSaved(true)
      toast.success(`${data.ticker} saved as idea`)
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  const errorInfo = error ? categorizeError(error) : null

  return (
    <div className="space-y-6">
      {/* Top row: Ticker input + Grade + Score */}
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <TickerInput
          onAnalyze={handleAnalyze}
          loading={isLoading}
          defaultTicker={ticker.toUpperCase()}
        />
        {data && (
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Score</p>
              <p className="text-lg font-bold font-mono">
                {data.green_flag.score}/{data.green_flag.max_score}
              </p>
            </div>
            <GradeBadge grade={data.green_flag.grade} size="lg" />
          </div>
        )}
        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="text-right space-y-1">
              <Skeleton className="h-3 w-8 ml-auto" />
              <Skeleton className="h-6 w-12 ml-auto" />
            </div>
            <Skeleton className="h-8 w-12 rounded-md" />
          </div>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && <IndicatorPanelSkeleton />}

      {/* Error state */}
      {error && !isLoading && (
        <ErrorDisplay
          message={errorInfo?.code === "BAD_REQUEST"
            ? `Invalid ticker "${ticker.toUpperCase()}"`
            : userMessage(errorInfo?.code ?? "UNKNOWN")}
          detail={errorInfo?.message}
          onRetry={() => refresh()}
        />
      )}

      {/* Data loaded */}
      {data && !isLoading && (
        <>
          <IndicatorPanel data={data} />

          <GreenFlagChecklist greenFlag={data.green_flag} />

          <div className="flex justify-end">
            <Button
              onClick={handleSaveIdea}
              disabled={saving || saved}
              variant={saved ? "outline" : "default"}
              className="gap-2"
            >
              {saving ? (
                <Loader2 className="size-4 animate-spin" />
              ) : saved ? (
                <CheckCircle2 className="size-4 text-emerald-400" />
              ) : (
                <Save className="size-4" />
              )}
              {saving ? "Saving..." : saved ? "Saved as Idea" : "Save as Idea"}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
