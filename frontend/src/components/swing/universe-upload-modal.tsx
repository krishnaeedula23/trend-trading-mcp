"use client"

import { useState } from "react"
import { Upload, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

interface Props {
  onUpload: (file: File, mode: "replace" | "add") => Promise<{ tickers_added: number; tickers_removed: number; total_active: number }>
}

export function UniverseUploadModal({ onUpload }: Props) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<"replace" | "add">("add")
  const [busy, setBusy] = useState(false)

  async function handleUpload() {
    if (!file) return
    setBusy(true)
    try {
      const r = await onUpload(file, mode)
      toast.success(`Added ${r.tickers_added}, removed ${r.tickers_removed}. Active: ${r.total_active}`)
      setOpen(false)
      setFile(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-8 text-xs"><Upload className="mr-1.5 size-3.5" /> Upload CSV</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Upload Deepvue Universe</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">CSV file</Label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-xs"
            />
            {file && <p className="text-[10px] text-muted-foreground">{file.name} ({file.size} bytes)</p>}
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Mode</Label>
            <RadioGroup value={mode} onValueChange={(v) => setMode(v as "replace" | "add")}>
              <div className="flex items-center gap-2"><RadioGroupItem value="add" id="add" /><Label htmlFor="add" className="text-xs">Add (merge with existing)</Label></div>
              <div className="flex items-center gap-2"><RadioGroupItem value="replace" id="replace" /><Label htmlFor="replace" className="text-xs">Replace (soft-delete old deepvue rows)</Label></div>
            </RadioGroup>
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
            <Button size="sm" onClick={handleUpload} disabled={!file || busy}>
              {busy ? <><Loader2 className="mr-1.5 size-3 animate-spin" /> Uploading</> : "Upload"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
