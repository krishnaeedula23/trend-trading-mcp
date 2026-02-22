"use client"

import { AlertTriangle, RefreshCw } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface ErrorDisplayProps {
  message: string
  detail?: string
  onRetry?: () => void
}

export function ErrorDisplay({ message, detail, onRetry }: ErrorDisplayProps) {
  return (
    <Card className="border-red-600/30 bg-red-600/5">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-10">
        <div className="flex size-10 items-center justify-center rounded-full bg-red-600/15">
          <AlertTriangle className="size-5 text-red-400" />
        </div>
        <div className="text-center space-y-1">
          <p className="text-sm font-medium text-red-400">{message}</p>
          {detail && (
            <p className="text-xs text-muted-foreground">{detail}</p>
          )}
        </div>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} className="gap-1.5">
            <RefreshCw className="size-3.5" />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
