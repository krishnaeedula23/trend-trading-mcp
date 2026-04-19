"use client"
import useSWR from "swr"
import type { SwingWeekGroup } from "@/lib/types"

const fetcher = (u: string) => fetch(u).then(r => r.json() as Promise<SwingWeekGroup[]>)

export function useSwingWeekly() {
  const { data, isLoading, error, mutate } = useSWR<SwingWeekGroup[]>("/api/swing/weekly", fetcher)
  return { weeks: data ?? [], isLoading, error, mutate }
}
