"use client"

import { useState } from "react"
import Link from "next/link"
import { Lightbulb, Plus } from "lucide-react"
import { toast } from "sonner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { IdeaCard } from "@/components/ideas/idea-card"
import { IdeaCardSkeleton } from "@/components/skeletons/idea-card-skeleton"
import { useIdeas, updateIdea, deleteIdea } from "@/hooks/use-ideas"
import type { IdeaStatus } from "@/lib/types"

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "watching", label: "Watching" },
  { value: "active", label: "Active" },
  { value: "triggered", label: "Triggered" },
  { value: "closed", label: "Closed" },
] as const

export default function IdeasPage() {
  const [activeTab, setActiveTab] = useState("all")
  const statusFilter = activeTab === "all" ? undefined : activeTab
  const { ideas, isLoading, refresh } = useIdeas(statusFilter)

  async function handleStatusChange(id: string, newStatus: string) {
    try {
      if (newStatus === "delete") {
        await deleteIdea(id)
        toast.success("Idea deleted")
      } else {
        await updateIdea(id, { status: newStatus as IdeaStatus })
        toast.success(`Idea marked as ${newStatus}`)
      }
      refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update idea")
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Trade Ideas</h1>
          <p className="text-sm text-muted-foreground">
            Track and manage your trade setups
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/analyze">
            <Plus className="size-4" />
            New Idea
          </Link>
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Loading skeletons */}
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <IdeaCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Ideas grid */}
      {!isLoading && ideas.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && ideas.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 py-20">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-muted">
            <Lightbulb className="size-6 text-muted-foreground" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm font-medium">No ideas yet</p>
            <p className="text-xs text-muted-foreground">
              {activeTab === "all"
                ? "Analyze a ticker and save it as a trade idea to get started."
                : `No ${activeTab} ideas found.`}
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/analyze">
              <Plus className="size-4" />
              Analyze a Ticker
            </Link>
          </Button>
        </div>
      )}
    </div>
  )
}
