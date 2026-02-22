"use client"

import { useState } from "react"
import { Search, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const TIMEFRAMES = [
  { value: "1m", label: "1m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1h" },
  { value: "4h", label: "4h" },
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
] as const

const DIRECTIONS = [
  { value: "bullish", label: "Bullish" },
  { value: "bearish", label: "Bearish" },
] as const

interface TickerInputProps {
  onAnalyze: (ticker: string, timeframe: string, direction: string) => void
  loading?: boolean
  defaultTicker?: string
}

export function TickerInput({
  onAnalyze,
  loading = false,
  defaultTicker = "",
}: TickerInputProps) {
  const [ticker, setTicker] = useState(defaultTicker)
  const [timeframe, setTimeframe] = useState("5m")
  const [direction, setDirection] = useState("bullish")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const cleaned = ticker.trim().toUpperCase()
    if (cleaned) {
      onAnalyze(cleaned, timeframe, direction)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      {/* Ticker input */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-muted-foreground">
          Ticker
        </label>
        <Input
          type="text"
          placeholder="SPY"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          className="h-9 w-28 font-mono text-sm uppercase"
          disabled={loading}
        />
      </div>

      {/* Timeframe select */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-muted-foreground">
          Timeframe
        </label>
        <Select value={timeframe} onValueChange={setTimeframe} disabled={loading}>
          <SelectTrigger className="h-9 w-20">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIMEFRAMES.map((tf) => (
              <SelectItem key={tf.value} value={tf.value}>
                {tf.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Direction select */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-muted-foreground">
          Direction
        </label>
        <Select value={direction} onValueChange={setDirection} disabled={loading}>
          <SelectTrigger className="h-9 w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIRECTIONS.map((d) => (
              <SelectItem key={d.value} value={d.value}>
                {d.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Analyze button */}
      <Button type="submit" disabled={loading || !ticker.trim()} className="h-9">
        {loading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Search className="size-4" />
        )}
        <span>{loading ? "Analyzing..." : "Analyze"}</span>
      </Button>
    </form>
  )
}
