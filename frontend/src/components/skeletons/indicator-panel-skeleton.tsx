import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function IndicatorCardSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center justify-between">
            <Skeleton className="h-3.5 w-20" />
            <Skeleton className="h-3.5 w-16" />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function IndicatorPanelSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <IndicatorCardSkeleton rows={8} />
      <IndicatorCardSkeleton rows={8} />
      <IndicatorCardSkeleton rows={3} />
      <IndicatorCardSkeleton rows={6} />
    </div>
  )
}
