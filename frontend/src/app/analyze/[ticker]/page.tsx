"use client"

import React, { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2, Save, CheckCircle2 } from "lucide-react"
import { TickerInput } from "@/components/analysis/ticker-input"
import { IndicatorPanel } from "@/components/analysis/indicator-panel"
import { GreenFlagChecklist } from "@/components/analysis/green-flag-checklist"
import { GradeBadge } from "@/components/ideas/grade-badge"
import { PhaseGauge } from "@/components/charts/phase-gauge"
import { RibbonIndicator } from "@/components/charts/ribbon-indicator"
import { useTradePlan } from "@/hooks/use-trade-plan"
import { createIdea } from "@/hooks/use-ideas"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default function AnalyzeTickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>
}) {
  const { ticker } = React.use(params)
  const router = useRouter()
  const searchParams = useSearchParams()

  const timeframe = searchParams.get("tf") ?? "5m"
  const direction = searchParams.get("dir") ?? "bullish"

  const { data, error, isLoading } = useTradePlan(ticker, timeframe, direction)

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
    } catch {
      // Error is silently handled; the button state resets
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Top row: Ticker input + Grade + Score */}
      <div className="flex flex-wrap items-end justify-between gap-4">
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
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center gap-3 py-20">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Analyzing {ticker.toUpperCase()}...
          </p>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-2 py-20">
          <p className="text-sm text-red-400">
            Failed to load analysis for {ticker.toUpperCase()}.
          </p>
          <p className="text-xs text-muted-foreground">
            Check that the ticker is valid and the API is running.
          </p>
        </div>
      )}

      {/* Data loaded */}
      {data && !isLoading && (
        <>
          {/* Indicator panel (4-card grid) */}
          <IndicatorPanel data={data} />

          {/* Third row: Green Flag + Phase/Ribbon */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left: Green Flag Checklist */}
            <GreenFlagChecklist greenFlag={data.green_flag} />

            {/* Right: Phase Gauge + Ribbon Indicator stacked */}
            <div className="space-y-4">
              <Card className="bg-card/50 border-border/50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Phase Oscillator</CardTitle>
                </CardHeader>
                <CardContent>
                  <PhaseGauge
                    oscillator={data.phase_oscillator.oscillator}
                    phase={data.phase_oscillator.phase}
                  />
                </CardContent>
              </Card>

              <Card className="bg-card/50 border-border/50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Pivot Ribbon</CardTitle>
                </CardHeader>
                <CardContent>
                  <RibbonIndicator ribbon={data.pivot_ribbon} />
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Save as Idea button */}
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
