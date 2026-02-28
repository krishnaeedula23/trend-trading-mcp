import { useCallback, useEffect, useRef, useState } from "react"
import useSWR from "swr"
import type { DailyPlanData } from "@/lib/daily-plan-types"

const STALE_THRESHOLD_MS = 12 * 60 * 60 * 1000 // 12 hours

async function fetcher(url: string): Promise<DailyPlanData | null> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
  return res.json()
}

export function useDailyPlan() {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const autoRefreshTriggered = useRef(false)

  const { data, error, isLoading, mutate } = useSWR<DailyPlanData | null>(
    "/api/trade-plan",
    fetcher,
    { refreshInterval: 0 },
  )

  // Auto-refresh on mount if data is stale or missing
  useEffect(() => {
    if (autoRefreshTriggered.current) return
    if (isLoading) return

    const shouldRefresh =
      !data ||
      data.instruments.length === 0 ||
      isStale(data.fetchedAt)

    if (shouldRefresh) {
      autoRefreshTriggered.current = true
      void doRefresh()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, isLoading])

  const doRefresh = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const res = await fetch("/api/trade-plan/generate", { method: "POST" })
      if (!res.ok) throw new Error(`Generate failed: ${res.status}`)
      const fresh: DailyPlanData = await res.json()
      await mutate(fresh, { revalidate: false })
    } catch (err) {
      console.error("Daily plan refresh error:", err)
    } finally {
      setIsRefreshing(false)
    }
  }, [mutate])

  return {
    data: data ?? null,
    isLoading,
    isRefreshing,
    error,
    refresh: doRefresh,
  }
}

function isStale(fetchedAt: string): boolean {
  const age = Date.now() - new Date(fetchedAt).getTime()
  return age > STALE_THRESHOLD_MS
}
