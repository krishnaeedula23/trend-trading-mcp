"use client"

import Link from "next/link"
import { ArrowUp, ArrowDown, MoreHorizontal, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { GradeBadge } from "@/components/ideas/grade-badge"
import type { Idea, IdeaStatus } from "@/lib/types"

function statusBadgeColor(status: IdeaStatus): string {
  switch (status) {
    case "watching":
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
    case "active":
      return "bg-blue-600/20 text-blue-400 border-blue-600/30"
    case "triggered":
      return "bg-emerald-600/20 text-emerald-400 border-emerald-600/30"
    case "closed":
      return "bg-zinc-600/20 text-zinc-400 border-zinc-600/30"
    case "expired":
      return "bg-amber-600/20 text-amber-400 border-amber-600/30"
  }
}

function relativeTime(dateStr: string): string {
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return "just now"
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  const diffMonth = Math.floor(diffDay / 30)
  return `${diffMonth}mo ago`
}

function formatPnl(pnl: number | null): React.ReactNode {
  if (pnl == null) return null
  const isPositive = pnl >= 0
  return (
    <span
      className={cn(
        "text-xs font-mono font-semibold",
        isPositive ? "text-emerald-400" : "text-red-400"
      )}
    >
      {isPositive ? "+" : ""}
      {pnl.toFixed(2)}
    </span>
  )
}

interface IdeaCardProps {
  idea: Idea
  onStatusChange?: (id: string, status: string) => void
}

export function IdeaCard({ idea, onStatusChange }: IdeaCardProps) {
  return (
    <Link href={`/ideas/${idea.id}`} className="block">
    <Card className="bg-card/50 border-border/50 hover:border-border transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          {/* Left: ticker + direction + grade */}
          <div className="flex items-center gap-2.5">
            {/* Direction arrow */}
            <div
              className={cn(
                "flex size-8 items-center justify-center rounded-lg",
                idea.direction === "bullish"
                  ? "bg-emerald-600/15"
                  : "bg-red-600/15"
              )}
            >
              {idea.direction === "bullish" ? (
                <ArrowUp className="size-4 text-emerald-400" />
              ) : (
                <ArrowDown className="size-4 text-red-400" />
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold font-mono">
                  {idea.ticker}
                </span>
                <GradeBadge grade={idea.grade} size="sm" />
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge
                  className={cn("text-[10px]", statusBadgeColor(idea.status))}
                >
                  {idea.status.toUpperCase()}
                </Badge>
                <span className="text-[10px] text-muted-foreground">
                  {idea.timeframe}
                </span>
              </div>
            </div>
          </div>

          {/* Right: price info + actions */}
          <div className="flex items-start gap-2">
            <div className="text-right">
              {idea.current_price != null && (
                <div className="text-sm font-mono font-medium">
                  ${idea.current_price.toFixed(2)}
                </div>
              )}
              {idea.entry_price != null && (
                <div className="text-[10px] text-muted-foreground">
                  Entry: ${idea.entry_price.toFixed(2)}
                </div>
              )}
              {formatPnl(idea.pnl)}
            </div>

            {/* Actions dropdown */}
            {onStatusChange && (
              <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon-xs" onClick={(e) => e.preventDefault()}>
                    <MoreHorizontal className="size-3.5" />
                    <span className="sr-only">Actions</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-36">
                  <DropdownMenuItem
                    onClick={(e) => { e.preventDefault(); onStatusChange(idea.id, "active") }}
                  >
                    Mark Active
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(e) => { e.preventDefault(); onStatusChange(idea.id, "triggered") }}
                  >
                    Mark Triggered
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={(e) => { e.preventDefault(); onStatusChange(idea.id, "closed") }}
                  >
                    Close
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={(e) => { e.preventDefault(); onStatusChange(idea.id, "delete") }}
                  >
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>

        {/* Footer: time */}
        <div className="mt-2.5 flex items-center gap-1 text-[10px] text-muted-foreground">
          <Clock className="size-3" />
          <span>{relativeTime(idea.created_at)}</span>
        </div>
      </CardContent>
    </Card>
    </Link>
  )
}
