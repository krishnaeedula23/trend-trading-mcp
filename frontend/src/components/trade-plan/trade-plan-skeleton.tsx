import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"

export function TradePlanSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
        <Skeleton className="h-9 w-24" />
      </div>

      {/* VIX bar skeleton */}
      <Skeleton className="h-14 w-full rounded-lg" />

      {/* Directional plan skeleton */}
      <Skeleton className="h-20 w-full rounded-lg" />

      {/* Two-column instrument panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[0, 1].map((i) => (
          <Card key={i} className="border-border/50 bg-card/50">
            <CardContent className="p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-6 w-12" />
                  <Skeleton className="h-6 w-20" />
                </div>
                <div className="flex gap-1.5">
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-5 w-16" />
                </div>
              </div>
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-px w-full" />
              <Skeleton className="h-12 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
