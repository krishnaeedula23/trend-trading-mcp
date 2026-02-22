"use client"

import React, { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, ArrowUp, ArrowDown, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useIdea } from "@/hooks/use-idea"
import { updateIdea, deleteIdea } from "@/hooks/use-ideas"
import { IdeaForm } from "@/components/ideas/idea-form"
import { GradeBadge } from "@/components/ideas/grade-badge"
import { IndicatorPanel } from "@/components/analysis/indicator-panel"
import { GreenFlagChecklist } from "@/components/analysis/green-flag-checklist"
import { ErrorDisplay } from "@/components/ui/error-display"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"
import { categorizeError } from "@/lib/errors"
import type { Idea, IdeaStatus, TradePlanResponse } from "@/lib/types"

const STATUS_OPTIONS: { value: IdeaStatus; label: string }[] = [
  { value: "watching", label: "Watching" },
  { value: "active", label: "Active" },
  { value: "triggered", label: "Triggered" },
  { value: "closed", label: "Closed" },
  { value: "expired", label: "Expired" },
]

export default function IdeaDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = React.use(params)
  const router = useRouter()
  const { idea, error, isLoading, refresh } = useIdea(id)
  const [deleting, setDeleting] = useState(false)

  async function handleStatusChange(newStatus: string) {
    try {
      await updateIdea(id, { status: newStatus as IdeaStatus })
      toast.success(`Status changed to ${newStatus}`)
      refresh()
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    }
  }

  async function handleSave(updates: Partial<Idea>) {
    try {
      await updateIdea(id, updates)
      toast.success("Idea saved")
      refresh()
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteIdea(id)
      toast.success("Idea deleted")
      router.push("/ideas")
    } catch (err) {
      const { message } = categorizeError(err)
      toast.error(message)
      setDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-5 w-24" />
        <div className="flex items-center gap-3">
          <Skeleton className="size-10 rounded-lg" />
          <Skeleton className="h-7 w-20" />
          <Skeleton className="h-7 w-12 rounded-md" />
        </div>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="p-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !idea) {
    return (
      <div className="space-y-6">
        <Link href="/ideas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" />
          Back to Ideas
        </Link>
        <ErrorDisplay
          message="Idea not found"
          detail="This idea may have been deleted."
          onRetry={() => refresh()}
        />
      </div>
    )
  }

  const snapshot = idea.indicator_snapshot as TradePlanResponse | null

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/ideas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="size-3.5" />
        Back to Ideas
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex size-10 items-center justify-center rounded-lg",
              idea.direction === "bullish" ? "bg-emerald-600/15" : "bg-red-600/15"
            )}
          >
            {idea.direction === "bullish" ? (
              <ArrowUp className="size-5 text-emerald-400" />
            ) : (
              <ArrowDown className="size-5 text-red-400" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold font-mono">{idea.ticker}</span>
              <GradeBadge grade={idea.grade} size="lg" />
              {idea.score != null && (
                <span className="text-sm text-muted-foreground font-mono">
                  {idea.score}/10
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge variant="outline" className="text-[10px]">
                {idea.timeframe}
              </Badge>
              <span className="text-xs text-muted-foreground capitalize">
                {idea.direction}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Select value={idea.status} onValueChange={handleStatusChange}>
            <SelectTrigger className="h-9 w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm" disabled={deleting} className="gap-1.5">
                <Trash2 className="size-3.5" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete idea?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete the {idea.ticker} {idea.direction} idea. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete}>
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Trade Parameters Form */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Trade Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <IdeaForm idea={idea} onSave={handleSave} />
        </CardContent>
      </Card>

      {/* Indicator Snapshot (read-only) */}
      {snapshot?.atr_levels && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold">Indicator Snapshot</h2>
          <IndicatorPanel data={snapshot} />
          {snapshot.green_flag && (
            <GreenFlagChecklist greenFlag={snapshot.green_flag} />
          )}
        </div>
      )}
    </div>
  )
}
