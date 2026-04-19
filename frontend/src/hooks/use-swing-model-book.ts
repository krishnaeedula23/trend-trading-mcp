"use client"
import useSWR from "swr"
import type { SwingModelBookEntry } from "@/lib/types"

type Filters = { setup_kell?: string; outcome?: string; ticker?: string }

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingModelBookEntry[]>)

export function useSwingModelBook(filters: Filters = {}) {
  const q = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v) as [string, string][],
  ).toString()
  const url = `/api/swing/model-book${q ? `?${q}` : ""}`
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry[]>(url, fetcher)
  return { entries: data ?? [], isLoading, error, mutate }
}

export function useSwingModelBookEntry(id: string | null) {
  const { data, isLoading, error, mutate } = useSWR<SwingModelBookEntry>(
    id ? `/api/swing/model-book/${id}` : null,
    (u: string) => fetch(u).then(r => r.json()),
  )
  return { entry: data, isLoading, error, mutate }
}
