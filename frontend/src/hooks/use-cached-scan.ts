"use client"

import { useEffect, useRef, useState } from "react"

interface CachedScanData<T> {
  results: T | null
  scanned_at: string | null
}

/**
 * Fetch cached scan results from Supabase on mount.
 * Returns { cachedData, cachedAt, loadingCache, refreshCache }.
 */
export function useCachedScan<T>(scanKey: string | null) {
  const [cachedData, setCachedData] = useState<T | null>(null)
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const [loadingCache, setLoadingCache] = useState(false)
  const fetched = useRef(false)

  const fetchCache = async (key: string) => {
    setLoadingCache(true)
    try {
      const res = await fetch(`/api/screener/cached?scan_key=${encodeURIComponent(key)}`)
      if (!res.ok) return
      const data: CachedScanData<T> = await res.json()
      if (data.results) {
        setCachedData(data.results)
        setCachedAt(data.scanned_at)
      }
    } catch {
      // cache miss is fine — user can run manual scan
    } finally {
      setLoadingCache(false)
    }
  }

  useEffect(() => {
    if (fetched.current || !scanKey) return
    fetched.current = true
    void fetchCache(scanKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanKey])

  const refreshCache = () => {
    if (!scanKey) return
    fetched.current = false
    void fetchCache(scanKey)
  }

  return { cachedData, cachedAt, loadingCache, refreshCache }
}
