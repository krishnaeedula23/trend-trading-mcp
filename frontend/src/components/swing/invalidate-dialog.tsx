"use client"
import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import type { SwingIdea } from "@/lib/types"

export function InvalidateDialog({ idea, onSaved }: { idea: SwingIdea; onSaved?: () => void }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const r = await fetch(`/api/swing/ideas/${idea.id}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "invalidation",
          summary: reason || "Marked invalidated",
          payload: { reason },
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? body.error ?? "failed")
      }
      toast.success("Invalidation note saved")
      setOpen(false)
      setReason("")
      onSaved?.()
    } catch (e) {
      toast.error(`Failed: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive">Log Invalidation Note</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Log invalidation note for {idea.ticker}</DialogTitle>
          <DialogDescription>
            Logs an invalidation event in the timeline. The idea&apos;s status is flipped to &apos;invalidated&apos; only by the post-market pipeline when a stop is violated.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Why is this idea invalid? (thesis broken, stop hit, etc.)"
          rows={4}
        />
        <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save Note"}</Button>
      </DialogContent>
    </Dialog>
  )
}
