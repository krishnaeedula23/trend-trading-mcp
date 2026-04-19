"use client"
import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"

export function NoteDialog({ ideaId, onSaved }: { ideaId: string; onSaved?: () => void }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const r = await fetch(`/api/swing/ideas/${ideaId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: "user_note", summary: text, payload: { text } }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? body.error ?? "failed")
      }
      toast.success("Note added")
      setOpen(false)
      setText("")
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
        <Button variant="outline">Add Note</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Add note</DialogTitle></DialogHeader>
        <Textarea
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Observation, concern, pivot…"
          rows={5}
        />
        <Button onClick={save} disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save"}</Button>
      </DialogContent>
    </Dialog>
  )
}
