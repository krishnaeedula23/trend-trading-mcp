"use client"
import { useSwingWeekly } from "@/hooks/use-swing-weekly"

export function WeeklyList() {
  const { weeks, isLoading } = useSwingWeekly()
  if (isLoading) return <div className="text-muted-foreground">Loading…</div>
  if (!weeks.length) return <div className="text-muted-foreground">No weekly syntheses yet.</div>

  return (
    <div className="space-y-3">
      {weeks.map((w, i) => (
        <details
          key={w.week_of}
          open={i === 0}
          className="rounded border bg-card/30 p-3"
        >
          <summary className="cursor-pointer font-medium">
            Week of {w.week_of} · {w.entries.length} ideas
          </summary>
          <div className="mt-2 space-y-2">
            {w.entries.map(e => (
              <div key={e.idea_id} className="rounded border p-3">
                <div className="text-sm font-semibold">
                  {e.ticker} · {e.cycle_stage ?? "—"} · {e.status}
                </div>
                <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                  {e.claude_analysis ?? "—"}
                </p>
              </div>
            ))}
          </div>
        </details>
      ))}
    </div>
  )
}
