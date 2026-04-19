"use client"
import useSWR from "swr"
import type { SwingSnapshot } from "@/lib/types"
import { jsonFetcher } from "@/lib/swr-fetcher"

export function useSwingSnapshots(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingSnapshot[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/snapshots` : null,
    jsonFetcher,
  )
  return { snapshots: data ?? [], isLoading, error, mutate }
}
