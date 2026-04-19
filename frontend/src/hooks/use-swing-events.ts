"use client"
import useSWR from "swr"
import type { SwingEvent } from "@/lib/types"
import { jsonFetcher } from "@/lib/swr-fetcher"

export function useSwingEvents(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingEvent[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/events` : null,
    jsonFetcher,
  )
  return { events: data ?? [], isLoading, error, mutate }
}
