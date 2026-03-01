"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOG", "AMD"]

export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const router = useRouter()

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  function navigate(ticker: string) {
    setOpen(false)
    setQuery("")
    router.push(`/analyze/${ticker.toUpperCase()}`)
  }

  const filtered = query.length > 0
    ? POPULAR_TICKERS.filter((t) => t.toLowerCase().startsWith(query.toLowerCase()))
    : POPULAR_TICKERS

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search ticker... (e.g. AAPL)"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {query.length > 0 && (
            <button
              className="w-full text-left px-2 py-1.5 text-sm"
              onClick={() => navigate(query)}
            >
              Analyze <span className="font-semibold">{query.toUpperCase()}</span>
            </button>
          )}
        </CommandEmpty>
        <CommandGroup heading="Popular">
          {filtered.map((ticker) => (
            <CommandItem key={ticker} value={ticker} onSelect={() => navigate(ticker)}>
              {ticker}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
