"use client"
import useSWR from "swr"
import type { SwingWeekGroup } from "@/lib/types"
import { jsonFetcher } from "@/lib/swr-fetcher"

export function useSwingWeekly() {
  const { data, isLoading, error, mutate } = useSWR<SwingWeekGroup[]>("/api/swing/weekly", jsonFetcher)
  return { weeks: data ?? [], isLoading, error, mutate }
}
