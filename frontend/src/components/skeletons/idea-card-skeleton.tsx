import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function IdeaCardSkeleton() {
  return (
    <Card className="bg-card/50 border-border/50">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Skeleton className="size-8 rounded-lg" />
            <div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-8 rounded-full" />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <Skeleton className="h-4 w-16 rounded-full" />
                <Skeleton className="h-3 w-6" />
              </div>
            </div>
          </div>
          <div className="text-right space-y-1">
            <Skeleton className="h-4 w-16 ml-auto" />
            <Skeleton className="h-3 w-20 ml-auto" />
          </div>
        </div>
        <div className="mt-2.5 flex items-center gap-1">
          <Skeleton className="size-3 rounded-full" />
          <Skeleton className="h-3 w-12" />
        </div>
      </CardContent>
    </Card>
  )
}
