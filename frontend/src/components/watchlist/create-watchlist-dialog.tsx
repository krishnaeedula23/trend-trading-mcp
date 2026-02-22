"use client"

import { useState } from "react"
import { Plus, X } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface CreateWatchlistDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (name: string, tickers: string[]) => Promise<void>
}

export function CreateWatchlistDialog({
  open,
  onOpenChange,
  onCreate,
}: CreateWatchlistDialogProps) {
  const [name, setName] = useState("")
  const [tickers, setTickers] = useState<string[]>([])
  const [newTicker, setNewTicker] = useState("")
  const [saving, setSaving] = useState(false)

  function handleAddTicker() {
    const cleaned = newTicker.trim().toUpperCase()
    if (cleaned && !tickers.includes(cleaned)) {
      setTickers([...tickers, cleaned])
      setNewTicker("")
    }
  }

  function handleRemoveTicker(ticker: string) {
    setTickers(tickers.filter((t) => t !== ticker))
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      handleAddTicker()
    }
  }

  async function handleCreate() {
    setSaving(true)
    try {
      await onCreate(name.trim(), tickers)
      setName("")
      setTickers([])
      setNewTicker("")
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Watchlist</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <Input
              placeholder="e.g. MAG7, SEMIS, HOT"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
          </div>

          {/* Add ticker */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Add Tickers</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. AAPL"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                onKeyDown={handleKeyDown}
                className="h-9 font-mono uppercase"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddTicker}
                disabled={!newTicker.trim()}
                className="h-9"
              >
                <Plus className="size-4" />
              </Button>
            </div>
          </div>

          {/* Ticker list */}
          <div className="space-y-1">
            {tickers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-2">
                No tickers added yet
              </p>
            ) : (
              tickers.map((ticker) => (
                <div
                  key={ticker}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 bg-muted/30"
                >
                  <span className="text-sm font-mono font-medium">{ticker}</span>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => handleRemoveTicker(ticker)}
                  >
                    <X className="size-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={saving || !name.trim()}
          >
            {saving ? "Creating..." : "Create Watchlist"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
