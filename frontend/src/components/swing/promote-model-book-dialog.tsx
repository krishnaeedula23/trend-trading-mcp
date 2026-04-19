"use client"
import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import type { SwingIdea } from "@/lib/types"

export function PromoteModelBookDialog({ idea, onSaved }: { idea: SwingIdea; onSaved?: () => void }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState(`${idea.ticker} ${idea.setup_kell} ${new Date().getFullYear()}`)
  const [narrative, setNarrative] = useState("")
  const [takeaways, setTakeaways] = useState("")
  const [outcome, setOutcome] = useState<"winner" | "loser" | "example" | "missed">("example")
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const r = await fetch("/api/swing/model-book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          ticker: idea.ticker,
          setup_kell: idea.setup_kell,
          outcome,
          source_idea_id: idea.id,
          narrative,
          key_takeaways: takeaways.split("\n").map(s => s.trim()).filter(Boolean),
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? body.error ?? "failed")
      }
      toast.success("Added to Model Book")
      setOpen(false)
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
        <Button>Promote to Model Book</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Promote to Model Book</DialogTitle></DialogHeader>
        <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" />
        <select
          value={outcome}
          onChange={e => setOutcome(e.target.value as typeof outcome)}
          className="rounded border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="winner">Winner</option>
          <option value="loser">Loser</option>
          <option value="example">Example</option>
          <option value="missed">Missed</option>
        </select>
        <Textarea
          value={narrative}
          onChange={e => setNarrative(e.target.value)}
          placeholder="Narrative — what happened, why it worked/failed"
          rows={5}
        />
        <Textarea
          value={takeaways}
          onChange={e => setTakeaways(e.target.value)}
          placeholder="Key takeaways (one per line)"
          rows={4}
        />
        <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Promote"}</Button>
      </DialogContent>
    </Dialog>
  )
}
