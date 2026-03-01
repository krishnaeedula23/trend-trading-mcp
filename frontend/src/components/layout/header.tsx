"use client"

import { usePathname, useRouter } from "next/navigation"
import { useState } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { MobileSidebar } from "@/components/layout/sidebar"
import { GlobalSearch } from "@/components/global-search"

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/trade-plan": "Daily Trade Plan",
  "/analyze": "Analyze",
  "/ideas": "Ideas",
  "/alerts": "Alerts",
}

function getPageTitle(pathname: string): string {
  // Exact match first
  if (pageTitles[pathname]) return pageTitles[pathname]

  // Check if it starts with a known path (e.g., /analyze/SPY)
  for (const [path, title] of Object.entries(pageTitles)) {
    if (pathname.startsWith(path)) return title
  }

  return "Saty Trading"
}

export function Header() {
  const pathname = usePathname()
  const router = useRouter()
  const [ticker, setTicker] = useState("")

  const title = getPageTitle(pathname)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const cleaned = ticker.trim().toUpperCase()
    if (cleaned) {
      router.push(`/analyze/${cleaned}`)
      setTicker("")
    }
  }

  return (
    <header className="flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 lg:px-6">
      {/* Mobile hamburger */}
      <MobileSidebar />

      {/* Page title */}
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Quick ticker search */}
      <form onSubmit={handleSubmit} className="relative w-48 sm:w-64">
        <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Quick search ticker..."
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          className="h-8 pl-8 text-xs"
        />
      </form>

      {/* Cmd+K shortcut hint */}
      <kbd className="hidden sm:inline-flex h-5 items-center gap-1 rounded border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
        <span className="text-xs">⌘</span>K
      </kbd>

      {/* Global search dialog (Cmd+K) */}
      <GlobalSearch />
    </header>
  )
}
