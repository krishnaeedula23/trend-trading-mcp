"use client"
import { useState } from "react"
import { upload } from "@vercel/blob/client"
import { toast } from "sonner"

type Props = {
  ideaId?: string
  eventId?: number
  modelBookId?: string
  onUploaded?: () => void
}

export function ChartUploadDropzone({ ideaId, eventId, modelBookId, onUploaded }: Props) {
  const [busy, setBusy] = useState(false)

  async function handleFile(file: File) {
    setBusy(true)
    try {
      const newBlob = await upload(`swing-charts/${Date.now()}-${file.name}`, file, {
        access: "public",
        handleUploadUrl: "/api/swing/blob/upload-token",
      })
      const lower = file.name.toLowerCase()
      const timeframe =
        lower.includes("weekly") ? "weekly" :
        lower.includes("60") ? "60m" :
        lower.includes("annotated") ? "annotated" : "daily"

      const r = await fetch("/api/swing/charts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url: newBlob.url,
          timeframe,
          source: "tradingview-upload",
          idea_id: ideaId,
          event_id: eventId,
          model_book_id: modelBookId,
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail ?? body.error ?? "upload failed")
      }
      toast.success("Chart uploaded")
      onUploaded?.()
    } catch (e) {
      toast.error(`Upload failed: ${(e as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <label className="flex cursor-pointer items-center justify-center rounded border-2 border-dashed border-border p-6 text-sm text-muted-foreground hover:bg-muted/40">
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        disabled={busy}
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />
      {busy ? "Uploading…" : "Drop a chart image, or click to browse"}
    </label>
  )
}
