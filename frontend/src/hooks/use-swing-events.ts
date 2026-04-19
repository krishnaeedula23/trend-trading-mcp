"use client"
import useSWR from "swr"
import type { SwingEvent } from "@/lib/types"

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingEvent[]>)

export function useSwingEvents(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingEvent[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/events` : null,
    fetcher,
  )
  return { events: data ?? [], isLoading, error, mutate }
}
