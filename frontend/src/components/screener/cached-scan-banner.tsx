"use client"

import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface CachedScanBannerProps {
  cachedAt: string | null
  loading: boolean
  onRefresh: () => void
}

export function CachedScanBanner({ cachedAt, loading, onRefresh }: CachedScanBannerProps) {
  if (!cachedAt) return null

  const date = new Date(cachedAt)
  const formatted = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  })

  return (
    <div className="flex items-center gap-2 rounded-md border border-border/50 bg-card/30 px-3 py-1.5 text-xs text-muted-foreground">
      <span>Premarket scan &middot; {formatted}</span>
      <Button
        size="sm"
        variant="ghost"
        className="h-5 gap-1 px-1.5 text-[10px]"
        onClick={onRefresh}
        disabled={loading}
      >
        <RefreshCw className={`size-3 ${loading ? "animate-spin" : ""}`} />
        Refresh
      </Button>
    </div>
  )
}
