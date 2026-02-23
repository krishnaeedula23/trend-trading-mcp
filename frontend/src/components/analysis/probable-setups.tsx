"use client"

import { useState } from "react"
import { Check, X, Save, Loader2, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { TradePlanResponse } from "@/lib/types"
import { detectSetups, type DetectedSetup, type SetupConfidence } from "@/lib/setups"
import { createIdea } from "@/hooks/use-ideas"
import { categorizeError } from "@/lib/errors"

// --- Color helpers ---

function confidenceStyle(c: SetupConfidence): string {
  switch (c) {
    case "strong":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "moderate":
      return "bg-blue-600/20 text-blue-400 border-blue-600/30"
    case "forming":
      return "bg-amber-600/20 text-amber-400 border-amber-600/30"
  }
}

function setupColorStyle(color: string): string {
  const map: Record<string, string> = {
    emerald: "border-l-emerald-500",
    teal: "border-l-teal-500",
    red: "border-l-red-500",
    blue: "border-l-blue-500",
    purple: "border-l-purple-500",
    yellow: "border-l-yellow-500",
    amber: "border-l-amber-500",
  }
  return map[color] ?? "border-l-zinc-500"
}

// --- Setup Card ---

function SetupCard({
  setup,
  data,
}: {
  setup: DetectedSetup
  data: TradePlanResponse
}) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await createIdea({
        ticker: data.ticker,
        direction: setup.direction,
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
        entry_price: setup.entryPrice,
        stop_loss: setup.stopPrice,
        target_1: setup.targetPrice,
        tags: [`setup:${setup.id}`],
        source: "analyze",
        indicator_snapshot: data as unknown as Record<string, unknown>,
      })
      setSaved(true)
      toast.success(`${data.ticker} saved as ${setup.name} idea`)
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border/50 bg-card/30 border-l-4 overflow-hidden",
        setupColorStyle(setup.color)
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">
            #{setup.number}
          </span>
          <span className="text-sm font-semibold">{setup.name}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge className={cn("text-[10px]", confidenceStyle(setup.confidence))}>
            {setup.confidence.toUpperCase()}
          </Badge>
          <Badge
            className={cn(
              "text-[10px]",
              setup.direction === "bullish"
                ? "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
                : "bg-red-600/20 text-red-400 border-red-600/30"
            )}
          >
            {setup.direction.toUpperCase()}
          </Badge>
        </div>
      </div>

      {/* Conditions */}
      <div className="px-4 pb-2 space-y-1">
        {setup.conditions.map((c, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            {c.met ? (
              <div className="flex size-4 items-center justify-center rounded-full bg-emerald-600/20">
                <Check className="size-2.5 text-emerald-400" />
              </div>
            ) : (
              <div className="flex size-4 items-center justify-center rounded-full bg-red-600/20">
                <X className="size-2.5 text-red-400" />
              </div>
            )}
            <span className={cn(c.met ? "text-foreground" : "text-muted-foreground")}>
              {c.label}
            </span>
            {!c.required && (
              <span className="text-[9px] text-muted-foreground/60">opt</span>
            )}
          </div>
        ))}
      </div>

      {/* Entry / Target / Stop */}
      <div className="mx-4 my-2 h-px bg-border/30" />
      <div className="px-4 pb-2 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Entry</span>
          <span className="font-mono text-foreground">{setup.entryZone}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Target</span>
          <span className="font-mono text-emerald-400">{setup.target}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Stop</span>
          <span className="font-mono text-red-400">{setup.stop}</span>
        </div>
      </div>

      {/* Save button */}
      <div className="flex justify-end px-4 pb-3">
        <Button
          size="sm"
          variant={saved ? "outline" : "secondary"}
          className="h-7 text-xs gap-1.5"
          disabled={saving || saved}
          onClick={handleSave}
        >
          {saving ? (
            <Loader2 className="size-3 animate-spin" />
          ) : saved ? (
            <CheckCircle2 className="size-3 text-emerald-400" />
          ) : (
            <Save className="size-3" />
          )}
          {saving ? "Saving..." : saved ? "Saved" : "Save as Idea"}
        </Button>
      </div>
    </div>
  )
}

// --- Main Component ---

interface ProbableSetupsProps {
  data: TradePlanResponse
}

export function ProbableSetups({ data }: ProbableSetupsProps) {
  const setups = detectSetups(data)

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Probable Setups</CardTitle>
          {setups.length > 0 && (
            <Badge variant="outline" className="text-[10px]">
              {setups.length} detected
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {setups.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No active setups — wait for ribbon alignment and pullback candle.
          </p>
        ) : (
          <div className="space-y-3">
            {setups.map((s) => (
              <SetupCard key={s.id} setup={s} data={data} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
