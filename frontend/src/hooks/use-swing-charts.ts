"use client"
import useSWR from "swr"
import type { SwingChart } from "@/lib/types"

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingChart[]>)

export function useSwingCharts(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingChart[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/charts` : null,
    fetcher,
  )
  return { charts: data ?? [], isLoading, error, mutate }
}
