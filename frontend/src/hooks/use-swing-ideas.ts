"use client"

import { useCallback, useEffect, useState } from "react"
import type { SwingIdea, SwingIdeaListResponse } from "@/lib/types"

interface UseSwingIdeasReturn {
  ideas: SwingIdea[]
  total: number
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useSwingIdeas(
  status?: "active" | "watching" | "exited" | "invalidated"
): UseSwingIdeasReturn {
  const [ideas, setIdeas] = useState<SwingIdea[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const qs = new URLSearchParams({ limit: "50" })
      if (status) qs.set("status", status)
      const res = await fetch(`/api/swing/ideas?${qs.toString()}`, { cache: "no-store" })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: SwingIdeaListResponse = await res.json()
      setIdeas(data.ideas)
      setTotal(data.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ideas")
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => { void refresh() }, [refresh])

  return { ideas, total, loading, error, refresh }
}
