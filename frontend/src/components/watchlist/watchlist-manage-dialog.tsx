"use client"

import { useState } from "react"
import { Plus, X, Trash2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Watchlist } from "@/lib/types"

interface WatchlistManageDialogProps {
  watchlist: Watchlist
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (data: { name?: string; tickers?: string[] }) => Promise<void>
  onDelete: () => Promise<void>
}

export function WatchlistManageDialog({
  watchlist,
  open,
  onOpenChange,
  onSave,
  onDelete,
}: WatchlistManageDialogProps) {
  const [name, setName] = useState(watchlist.name)
  const [tickers, setTickers] = useState<string[]>(watchlist.tickers)
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

  async function handleSave() {
    setSaving(true)
    try {
      await onSave({ name, tickers })
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Manage Watchlist</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
          </div>

          {/* Add ticker */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Add Ticker</label>
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
                No tickers added
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

        <DialogFooter className="flex-row justify-between sm:justify-between">
          <Button
            variant="destructive"
            size="sm"
            onClick={onDelete}
            className="gap-1.5"
          >
            <Trash2 className="size-3.5" />
            Delete
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
