"use client"

import { useState, useEffect } from "react"
import { Save, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { Idea } from "@/lib/types"

interface IdeaFormProps {
  idea: Idea
  onSave: (updates: Partial<Idea>) => Promise<void>
}

export function IdeaForm({ idea, onSave }: IdeaFormProps) {
  const [entryPrice, setEntryPrice] = useState(idea.entry_price?.toString() ?? "")
  const [stopLoss, setStopLoss] = useState(idea.stop_loss?.toString() ?? "")
  const [target1, setTarget1] = useState(idea.target_1?.toString() ?? "")
  const [target2, setTarget2] = useState(idea.target_2?.toString() ?? "")
  const [filledPrice, setFilledPrice] = useState(idea.filled_price?.toString() ?? "")
  const [exitPrice, setExitPrice] = useState(idea.exit_price?.toString() ?? "")
  const [pnl, setPnl] = useState(idea.pnl?.toString() ?? "")
  const [notes, setNotes] = useState(idea.notes ?? "")
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    setEntryPrice(idea.entry_price?.toString() ?? "")
    setStopLoss(idea.stop_loss?.toString() ?? "")
    setTarget1(idea.target_1?.toString() ?? "")
    setTarget2(idea.target_2?.toString() ?? "")
    setFilledPrice(idea.filled_price?.toString() ?? "")
    setExitPrice(idea.exit_price?.toString() ?? "")
    setPnl(idea.pnl?.toString() ?? "")
    setNotes(idea.notes ?? "")
    setDirty(false)
  }, [idea])

  function parseNum(v: string): number | null {
    const n = parseFloat(v)
    return isNaN(n) ? null : n
  }

  function markDirty<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v)
      setDirty(true)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await onSave({
        entry_price: parseNum(entryPrice),
        stop_loss: parseNum(stopLoss),
        target_1: parseNum(target1),
        target_2: parseNum(target2),
        filled_price: parseNum(filledPrice),
        exit_price: parseNum(exitPrice),
        pnl: parseNum(pnl),
        notes: notes || null,
      })
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Entry Price" value={entryPrice} onChange={markDirty(setEntryPrice)} type="number" />
        <Field label="Stop Loss" value={stopLoss} onChange={markDirty(setStopLoss)} type="number" />
        <Field label="Target 1" value={target1} onChange={markDirty(setTarget1)} type="number" />
        <Field label="Target 2" value={target2} onChange={markDirty(setTarget2)} type="number" />
        <Field label="Filled Price" value={filledPrice} onChange={markDirty(setFilledPrice)} type="number" />
        <Field label="Exit Price" value={exitPrice} onChange={markDirty(setExitPrice)} type="number" />
        <Field label="P&L" value={pnl} onChange={markDirty(setPnl)} type="number" />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">Notes</label>
        <Textarea
          value={notes}
          onChange={(e) => markDirty(setNotes)(e.target.value)}
          placeholder="Trade notes..."
          rows={3}
          className="resize-none"
        />
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={!dirty || saving} size="sm" className="gap-1.5">
          {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <Input
        type={type}
        step={type === "number" ? "0.01" : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 font-mono"
      />
    </div>
  )
}
