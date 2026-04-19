"use client"
import useSWR from "swr"
import type { SwingModelBookEntry } from "@/lib/types"
import { jsonFetcher } from "@/lib/swr-fetcher"

type Filters = { setup_kell?: string; outcome?: string; ticker?: string }

export function useSwingModelBook(filters: Filters = {}) {
  const q = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v) as [string, string][],
  ).toString()
  const url = `/api/swing/model-book${q ? `?${q}` : ""}`
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry[]>(url, jsonFetcher)
  return { entries: data ?? [], isLoading, error, mutate }
}

export function useSwingModelBookEntry(id: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry>(
    id ? `/api/swing/model-book/${id}` : null,
    jsonFetcher,
  )
  return { entry: data, isLoading, error, mutate }
}
