"use client"
import useSWR from "swr"
import type { SwingSnapshot } from "@/lib/types"

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingSnapshot[]>)

export function useSwingSnapshots(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingSnapshot[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/snapshots` : null,
    fetcher,
  )
  return { snapshots: data ?? [], isLoading, error, mutate }
}
