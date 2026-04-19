"use client"
import { useState } from "react"
import { useSwingCharts } from "@/hooks/use-swing-charts"
import type { SwingChart } from "@/lib/types"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { ChartUploadDropzone } from "./chart-upload-dropzone"

const TFS = ["daily", "weekly", "60m", "annotated", "uploads"] as const
type TF = (typeof TFS)[number]

function chartMatchesTab(c: SwingChart, tab: TF): boolean {
  if (tab === "uploads") return c.source === "tradingview-upload" || c.source === "user-markup"
  if (tab === "annotated") return c.timeframe === "annotated" || c.source === "claude-annotated"
  return c.timeframe === tab
}

export function ChartGallery({ ideaId }: { ideaId: string }) {
  const { charts, mutate } = useSwingCharts(ideaId)
  const [lightbox, setLightbox] = useState<SwingChart | null>(null)

  return (
    <div className="space-y-4">
      <ChartUploadDropzone ideaId={ideaId} onUploaded={() => mutate()} />
      <Tabs defaultValue="daily">
        <TabsList>{TFS.map(t => <TabsTrigger key={t} value={t}>{t}</TabsTrigger>)}</TabsList>
        {TFS.map(tab => (
          <TabsContent key={tab} value={tab}>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {charts.filter(c => chartMatchesTab(c, tab)).map(c => (
                <button
                  key={c.id}
                  onClick={() => setLightbox(c)}
                  className="overflow-hidden rounded border"
                  type="button"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={c.thumbnail_url ?? c.image_url}
                    alt={c.caption ?? c.timeframe}
                    className="h-auto w-full"
                  />
                  {c.caption && <div className="p-1 text-xs text-muted-foreground">{c.caption}</div>}
                </button>
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setLightbox(null)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={lightbox.image_url}
            alt={lightbox.caption ?? ""}
            className="max-h-full max-w-full object-contain"
          />
        </div>
      )}
    </div>
  )
}
