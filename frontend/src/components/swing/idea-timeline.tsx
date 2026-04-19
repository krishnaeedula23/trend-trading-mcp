"use client"
import { useSwingEvents } from "@/hooks/use-swing-events"

const ICONS: Record<string, string> = {
  stage_transition: "🔄",
  thesis_updated: "📝",
  setup_fired: "🎯",
  invalidation: "🛑",
  earnings: "📊",
  exhaustion_warning: "⚠️",
  user_note: "🗒️",
  chart_uploaded: "🖼️",
  trade_recorded: "💵",
  promoted_to_model_book: "⭐",
}

function relativeTime(iso: string): string {
  const delta = Date.now() - new Date(iso).getTime()
  const secs = Math.max(1, Math.round(delta / 1000))
  if (secs < 60) return `${secs}s ago`
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  const weeks = Math.round(days / 7)
  if (weeks < 5) return `${weeks}w ago`
  const months = Math.round(days / 30)
  return months < 12 ? `${months}mo ago` : `${Math.round(months / 12)}y ago`
}

export function IdeaTimeline({ ideaId }: { ideaId: string }) {
  const { events, isLoading } = useSwingEvents(ideaId)
  if (isLoading) return <div className="text-muted-foreground">Loading timeline…</div>
  if (!events.length) return <div className="text-muted-foreground">No events yet.</div>

  return (
    <ol className="space-y-3">
      {events.map(e => (
        <li key={e.id} className="flex gap-3 border-l border-border pl-4 pb-3">
          <span className="text-xl" aria-hidden>{ICONS[e.event_type] ?? "•"}</span>
          <div>
            <div className="text-sm font-medium">{e.summary ?? e.event_type}</div>
            <div className="text-xs text-muted-foreground">
              {relativeTime(e.occurred_at)}
              {" · "}
              <code>{e.event_type}</code>
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}
