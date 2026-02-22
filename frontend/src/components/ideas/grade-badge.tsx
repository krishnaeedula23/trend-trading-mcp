import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

interface GradeBadgeProps {
  grade: string | null
  size?: "sm" | "md" | "lg"
}

function gradeColors(grade: string | null): string {
  switch (grade) {
    case "A+":
      return "bg-emerald-600 text-white border-emerald-500"
    case "A":
      return "bg-blue-600 text-white border-blue-500"
    case "B":
      return "bg-yellow-500 text-zinc-900 border-yellow-400"
    case "skip":
      return "bg-red-600 text-white border-red-500"
    default:
      return "bg-zinc-600 text-zinc-300 border-zinc-500"
  }
}

function sizeClasses(size: "sm" | "md" | "lg"): string {
  switch (size) {
    case "sm":
      return "text-[10px] px-1.5 py-0"
    case "md":
      return "text-xs px-2 py-0.5"
    case "lg":
      return "text-sm px-3 py-1 font-bold"
  }
}

export function GradeBadge({ grade, size = "md" }: GradeBadgeProps) {
  const label = grade === "skip" ? "SKIP" : grade ?? "N/A"

  return (
    <Badge className={cn("font-semibold", gradeColors(grade), sizeClasses(size))}>
      {label}
    </Badge>
  )
}
