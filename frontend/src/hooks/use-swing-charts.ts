"use client"
import useSWR from "swr"
import type { SwingChart } from "@/lib/types"
import { jsonFetcher } from "@/lib/swr-fetcher"

export function useSwingCharts(ideaId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingChart[]>(
    ideaId ? `/api/swing/ideas/${ideaId}/charts` : null,
    jsonFetcher,
  )
  return { charts: data ?? [], isLoading, error, mutate }
}

export function useSwingModelBookCharts(modelBookId: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingChart[]>(
    modelBookId ? `/api/swing/model-book/${modelBookId}/charts` : null,
    jsonFetcher,
  )
  return { charts: data ?? [], isLoading, error, mutate }
}
