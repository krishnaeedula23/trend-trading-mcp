"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Search,
  Radar,
  Lightbulb,
  List,
  Bell,
  TrendingUp,
  BarChart3,
  Menu,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Trade Plan", href: "/trade-plan", icon: BarChart3 },
  { label: "Analyze", href: "/analyze", icon: Search },
  { label: "Scan", href: "/scan", icon: Radar },
  { label: "Ideas", href: "/ideas", icon: Lightbulb },
  { label: "Watchlists", href: "/watchlists", icon: List },
  { label: "Alerts", href: "/alerts", icon: Bell, badge: "Soon" },
] as const

function NavLink({
  item,
  active,
  onClick,
}: {
  item: (typeof navItems)[number]
  active: boolean
  onClick?: () => void
}) {
  const Icon = item.icon
  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span>{item.label}</span>
      {"badge" in item && item.badge && (
        <Badge
          variant="secondary"
          className="ml-auto text-[10px] px-1.5 py-0"
        >
          {item.badge}
        </Badge>
      )}
    </Link>
  )
}

function SidebarContent({ onNavClick }: { onNavClick?: () => void }) {
  const pathname = usePathname()

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-600">
          <TrendingUp className="size-4 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight">Saty Trading</h1>
          <p className="text-[10px] text-muted-foreground">Trend Analysis</p>
        </div>
      </div>

      <Separator />

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname.startsWith(item.href)}
              onClick={onNavClick}
            />
          ))}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <Separator />
      <div className="px-4 py-3">
        <p className="text-[10px] text-muted-foreground">
          Saty + Maverick
        </p>
      </div>
    </div>
  )
}

/** Desktop sidebar - always visible on lg+ screens */
export function Sidebar() {
  return (
    <aside className="hidden lg:flex lg:w-60 lg:flex-col lg:border-r bg-sidebar text-sidebar-foreground">
      <SidebarContent />
    </aside>
  )
}

/** Mobile sidebar - triggered by hamburger button */
export function MobileSidebar() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="lg:hidden">
          <Menu className="size-5" />
          <span className="sr-only">Toggle menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent
        side="left"
        className="w-60 p-0 bg-sidebar text-sidebar-foreground"
        showCloseButton={false}
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Navigation</SheetTitle>
        </SheetHeader>
        <SidebarContent />
      </SheetContent>
    </Sheet>
  )
}
