"use client"
import { use } from "react"
import { useSwingIdeaDetail } from "@/hooks/use-swing-idea-detail"
import { IdeaHeader } from "@/components/swing/idea-header"
import { ThesisPanel } from "@/components/swing/thesis-panel"
import { IdeaTimeline } from "@/components/swing/idea-timeline"

export default function SwingIdeaDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { idea, error, isLoading } = useSwingIdeaDetail(id)

  if (isLoading) return <div className="p-6">Loading…</div>
  if (error) return <div className="p-6 text-destructive">Error: {error.message}</div>
  if (!idea) return <div className="p-6">Not found.</div>

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <IdeaHeader idea={idea} />
      <ThesisPanel idea={idea} />
      <IdeaTimeline ideaId={id} />
      {/* Plan 4 adds: ChartsGallery, FundamentalsPanel, ModelBookPromote */}
    </div>
  )
}
