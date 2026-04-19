"use client"
import { use } from "react"
import { useSwingIdeaDetail } from "@/hooks/use-swing-idea-detail"
import { IdeaHeader } from "@/components/swing/idea-header"
import { ThesisPanel } from "@/components/swing/thesis-panel"
import { IdeaTimeline } from "@/components/swing/idea-timeline"
import { ChartGallery } from "@/components/swing/chart-gallery"
import { IdeaActions } from "@/components/swing/idea-actions"

export default function SwingIdeaDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { idea, error, isLoading, refresh } = useSwingIdeaDetail(id)

  if (isLoading) return <div className="p-6">Loading…</div>
  if (error) return <div className="p-6 text-destructive">Error: {error.message}</div>
  if (!idea) return <div className="p-6">Not found.</div>

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <IdeaHeader idea={idea} />
      <IdeaActions idea={idea} onChanged={() => refresh()} />

      <section id="thesis">
        <h2 className="mb-2 text-lg font-semibold">Thesis</h2>
        <ThesisPanel idea={idea} />
      </section>

      <section id="timeline">
        <h2 className="mb-2 text-lg font-semibold">Timeline</h2>
        <IdeaTimeline ideaId={id} />
      </section>

      <section id="charts">
        <h2 className="mb-2 text-lg font-semibold">Charts</h2>
        <ChartGallery ideaId={id} />
      </section>

      {idea.next_earnings_date && (
        <section id="fundamentals">
          <h2 className="mb-2 text-lg font-semibold">Fundamentals</h2>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Next earnings</dt>
            <dd>{idea.next_earnings_date}</dd>
          </dl>
        </section>
      )}
    </div>
  )
}
