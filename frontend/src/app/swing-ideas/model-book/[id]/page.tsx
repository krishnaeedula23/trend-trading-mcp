"use client"
import { use } from "react"
import { useSwingModelBookEntry } from "@/hooks/use-swing-model-book"
import { ChartGallery } from "@/components/swing/chart-gallery"

export default function ModelBookDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { entry, isLoading } = useSwingModelBookEntry(id)

  if (isLoading) return <div className="p-6">Loading…</div>
  if (!entry) return <div className="p-6">Not found.</div>

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{entry.title}</h1>
        <div className="text-sm text-muted-foreground">
          {entry.ticker} · {entry.setup_kell} · {entry.outcome}
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Narrative</h2>
        <p className="whitespace-pre-wrap">{entry.narrative ?? "—"}</p>
      </section>

      {entry.key_takeaways?.length ? (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Key takeaways</h2>
          <ul className="list-disc pl-6">
            {entry.key_takeaways.map((k, i) => <li key={i}>{k}</li>)}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className="mb-2 text-lg font-semibold">Charts</h2>
        <ChartGallery modelBookId={entry.id} />
      </section>
    </div>
  )
}
