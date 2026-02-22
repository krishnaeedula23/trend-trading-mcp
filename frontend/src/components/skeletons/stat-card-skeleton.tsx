import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function StatCardSkeleton() {
  return (
    <Card className="bg-card/50 border-border/50">
      <CardContent className="flex items-center gap-4 p-4">
        <Skeleton className="size-10 rounded-lg" />
        <div className="space-y-1.5">
          <Skeleton className="h-6 w-8" />
          <Skeleton className="h-3 w-16" />
        </div>
      </CardContent>
    </Card>
  )
}
