"use client"

import { useState } from "react"
import { Check, X, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { GreenFlag, Grade, RibbonState, MtfRibbonEntry } from "@/lib/types"

function gradeStyle(grade: Grade): string {
  switch (grade) {
    case "A+":
      return "bg-emerald-600 text-white border-emerald-500"
    case "A":
      return "bg-blue-600 text-white border-blue-500"
    case "B":
      return "bg-yellow-500 text-zinc-900 border-yellow-400"
    case "skip":
      return "bg-red-600 text-white border-red-500"
  }
}

function formatFlagName(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const TF_LABELS: Record<string, string> = {
  "1m": "1m", "5m": "5m", "15m": "15m",
  "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W",
}

function ribbonDotColor(state: RibbonState): string {
  switch (state) {
    case "bullish":
      return "bg-emerald-500"
    case "bearish":
      return "bg-red-500"
    case "chopzilla":
      return "bg-yellow-500"
  }
}

interface GreenFlagChecklistProps {
  greenFlag: GreenFlag
  currentTimeframe?: string
  currentRibbonState?: RibbonState
  mtfRibbons?: Record<string, MtfRibbonEntry>
}

export function GreenFlagChecklist({
  greenFlag,
  currentTimeframe,
  currentRibbonState,
  mtfRibbons,
}: GreenFlagChecklistProps) {
  const [auditOpen, setAuditOpen] = useState(false)

  const flagEntries = Object.entries(greenFlag.flags)

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Green Flag Grade</CardTitle>
          <div className="flex items-center gap-2">
            {/* Score */}
            <span className="text-sm font-mono text-muted-foreground">
              {greenFlag.score}/{greenFlag.max_score}
            </span>
            {/* Grade badge */}
            <Badge
              className={cn(
                "text-sm font-bold px-3 py-0.5",
                gradeStyle(greenFlag.grade)
              )}
            >
              {greenFlag.grade === "skip"
                ? "SKIP"
                : greenFlag.grade}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Flag checklist */}
        <div className="space-y-1.5">
          {flagEntries.map(([key, value]) => {
            // MTF aligned row — show inline ribbon dots
            if (key === "mtf_aligned" && mtfRibbons && currentTimeframe && currentRibbonState) {
              const entries = [
                { tf: currentTimeframe, state: currentRibbonState, isCurrent: true },
                ...Object.entries(mtfRibbons).map(([tf, r]) => ({
                  tf,
                  state: r.ribbon_state,
                  isCurrent: false,
                })),
              ]
              return (
                <div key={key} className="flex items-center gap-2.5 text-sm">
                  {value === true ? (
                    <div className="flex size-5 items-center justify-center rounded-full bg-emerald-600/20">
                      <Check className="size-3 text-emerald-400" />
                    </div>
                  ) : (
                    <div className="flex size-5 items-center justify-center rounded-full bg-red-600/20">
                      <X className="size-3 text-red-400" />
                    </div>
                  )}
                  <span className={cn(value ? "text-foreground" : "text-muted-foreground")}>
                    MTF
                  </span>
                  <div className="flex items-center gap-1 ml-1">
                    {entries.map(({ tf, state, isCurrent }) => (
                      <div
                        key={tf}
                        className={cn(
                          "flex items-center gap-1 rounded px-1.5 py-0.5",
                          isCurrent ? "ring-1 ring-primary/40 bg-primary/5" : "bg-muted/30"
                        )}
                      >
                        <div className={cn("size-2 rounded-full", ribbonDotColor(state))} />
                        <span className="text-[10px] font-mono">{TF_LABELS[tf] ?? tf}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            }

            return (
              <div
                key={key}
                className="flex items-center gap-2.5 text-sm"
              >
                {value === true ? (
                  <div className="flex size-5 items-center justify-center rounded-full bg-emerald-600/20">
                    <Check className="size-3 text-emerald-400" />
                  </div>
                ) : value === false ? (
                  <div className="flex size-5 items-center justify-center rounded-full bg-red-600/20">
                    <X className="size-3 text-red-400" />
                  </div>
                ) : (
                  <div className="flex size-5 items-center justify-center rounded-full bg-zinc-600/20">
                    <span className="text-[10px] text-zinc-500">--</span>
                  </div>
                )}
                <span
                  className={cn(
                    value === true
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {formatFlagName(key)}
                </span>
              </div>
            )
          })}
        </div>

        {/* Recommendation */}
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-xs text-muted-foreground leading-relaxed">
            {greenFlag.recommendation}
          </p>
        </div>

        {/* Collapsible verbal audit */}
        {greenFlag.verbal_audit && (
          <div>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setAuditOpen(!auditOpen)}
            >
              <span>Verbal Audit</span>
              {auditOpen ? (
                <ChevronUp className="size-3.5" />
              ) : (
                <ChevronDown className="size-3.5" />
              )}
            </Button>
            {auditOpen && (
              <div className="mt-1 rounded-lg bg-muted/30 p-3">
                <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {greenFlag.verbal_audit}
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
