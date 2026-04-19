"use client"
import type { SwingIdeaDetail } from "@/lib/types"

export function ThesisPanel({ idea }: { idea: SwingIdeaDetail }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Thesis
      </h2>

      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium">Base</span>
            {idea.thesis_status === "pending" && (
              <span className="text-xs rounded bg-amber-500/20 text-amber-700 dark:text-amber-300 px-1.5 py-0.5">
                pending
              </span>
            )}
            {idea.base_thesis_at && (
              <span className="text-xs text-muted-foreground">
                {new Date(idea.base_thesis_at).toLocaleString()}
              </span>
            )}
          </div>
          {idea.base_thesis ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{idea.base_thesis}</p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              Base thesis not yet generated. Runs at 6:30am PT on weekdays.
            </p>
          )}
        </div>

        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium">Deep</span>
            {idea.deep_thesis_at && (
              <span className="text-xs text-muted-foreground">
                {new Date(idea.deep_thesis_at).toLocaleString()}
              </span>
            )}
          </div>
          {idea.deep_thesis ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{idea.deep_thesis}</p>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              Deep analysis (Deepvue + charts) runs at 2:30pm PT. (Plan 4.)
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
