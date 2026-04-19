"use client"
import type { SwingIdea } from "@/lib/types"
import { NoteDialog } from "./note-dialog"
import { InvalidateDialog } from "./invalidate-dialog"
import { PromoteModelBookDialog } from "./promote-model-book-dialog"

export function IdeaActions({ idea, onChanged }: { idea: SwingIdea; onChanged?: () => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      <NoteDialog ideaId={idea.id} onSaved={onChanged} />
      <InvalidateDialog idea={idea} onSaved={onChanged} />
      <PromoteModelBookDialog idea={idea} onSaved={onChanged} />
    </div>
  )
}
