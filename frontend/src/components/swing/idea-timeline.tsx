"use client"
import type { SwingEvent } from "@/lib/types"

export function IdeaTimeline({ events }: { events: SwingEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Timeline
        </h2>
        <p className="text-sm text-muted-foreground italic">
          No events yet. Daily snapshots, stage transitions, and user notes will appear here.
        </p>
      </section>
    )
  }
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Timeline
      </h2>
      <ol className="space-y-2">
        {events.map((e) => (
          <li key={e.id} className="flex gap-3 text-sm">
            <span className="text-xs text-muted-foreground w-32 shrink-0">
              {new Date(e.occurred_at).toLocaleString()}
            </span>
            <span className="text-xs rounded bg-secondary px-1.5 py-0.5 h-fit">{e.event_type}</span>
            <span className="text-sm">{e.summary || ""}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
