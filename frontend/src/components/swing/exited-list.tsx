"use client"
import Link from "next/link"
import { useSwingIdeas } from "@/hooks/use-swing-ideas"
import { PromoteModelBookDialog } from "./promote-model-book-dialog"

export function ExitedList() {
  const { ideas: exited, loading: loadA } = useSwingIdeas("exited")
  const { ideas: invalidated, loading: loadB } = useSwingIdeas("invalidated")
  const isLoading = loadA || loadB
  const ideas = [...exited, ...invalidated].sort(
    (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime(),
  )

  if (isLoading && ideas.length === 0) return <div className="text-muted-foreground">Loading…</div>
  if (!ideas.length) return <div className="text-muted-foreground">No exited or invalidated ideas yet.</div>

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="py-2">Ticker</th>
          <th>Setup</th>
          <th>Outcome</th>
          <th>Stage</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {ideas.map(i => (
          <tr key={i.id} className="border-t">
            <td className="py-2">
              <Link href={`/swing-ideas/${i.id}`} className="font-medium hover:underline">
                {i.ticker}
              </Link>
            </td>
            <td>{i.setup_kell}</td>
            <td>{i.status === "exited" ? "Exited" : "Invalidated"}</td>
            <td>{i.cycle_stage}</td>
            <td className="text-right">
              <PromoteModelBookDialog idea={i} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
