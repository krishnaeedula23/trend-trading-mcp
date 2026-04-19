import useSWR from "swr"
import type { SwingIdeaDetail } from "@/lib/types"

const fetcher = async (url: string): Promise<SwingIdeaDetail> => {
  const r = await fetch(url, { cache: "no-store" })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error((body as { error?: string }).error || `Failed: ${r.status}`)
  }
  const data = await r.json()
  // Plan 2's endpoint doesn't embed events; Plan 4 will. Default to [].
  return { ...data, events: data.events ?? [] }
}

export function useSwingIdeaDetail(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SwingIdeaDetail>(
    id ? `/api/swing/ideas/${id}` : null,
    fetcher,
    { revalidateOnFocus: false, refreshInterval: 0 },
  )
  return { idea: data, error, isLoading, refresh: mutate }
}
