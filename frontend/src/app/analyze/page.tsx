"use client"

import { useRouter } from "next/navigation"
import { Search } from "lucide-react"
import { TickerInput } from "@/components/analysis/ticker-input"

export default function AnalyzePage() {
  const router = useRouter()

  function handleAnalyze(ticker: string, timeframe: string, direction: string, useCurrentClose: boolean | null) {
    const params = new URLSearchParams({ tf: timeframe, dir: direction })
    if (useCurrentClose === true) {
      params.set("ucc", "1")
    }
    router.push(`/analyze/${ticker}?${params.toString()}`)
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 py-20">
      {/* Icon */}
      <div className="flex size-16 items-center justify-center rounded-2xl bg-primary/10">
        <Search className="size-7 text-primary" />
      </div>

      {/* Heading */}
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Analyze a Ticker</h1>
        <p className="text-sm text-muted-foreground max-w-md">
          Enter a ticker symbol to analyze with Saty indicators. Get ATR levels,
          pivot ribbon state, phase oscillator readings, and a Green Flag trade
          grade.
        </p>
      </div>

      {/* Input */}
      <TickerInput onAnalyze={handleAnalyze} />
    </div>
  )
}
