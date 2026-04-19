"use client"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UniverseManager } from "@/components/swing/universe-manager"
import { IdeasList } from "@/components/swing/ideas-list"
import { MarketHealthBar } from "@/components/swing/market-health-bar"
import { ExitedList } from "@/components/swing/exited-list"

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-8 text-center">
      <p className="text-sm text-muted-foreground">{name} — coming in a later plan</p>
    </div>
  )
}

export default function SwingIdeasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Swing Ideas</h1>
        <p className="text-xs text-muted-foreground">Kell + Saty unified swing setups — detection, analysis, tracking</p>
      </div>

      <MarketHealthBar />

      <Tabs defaultValue="universe" className="space-y-4">
        <TabsList>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="watching">Watching</TabsTrigger>
          <TabsTrigger value="exited">Exited</TabsTrigger>
          <TabsTrigger value="universe">Universe</TabsTrigger>
          <TabsTrigger value="model-book" disabled>Model Book <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
          <TabsTrigger value="weekly" disabled>Weekly <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
        </TabsList>

        <TabsContent value="active"><IdeasList status="active" /></TabsContent>
        <TabsContent value="watching"><IdeasList status="watching" /></TabsContent>
        <TabsContent value="exited"><ExitedList /></TabsContent>
        <TabsContent value="universe"><UniverseManager /></TabsContent>
        <TabsContent value="model-book"><ComingSoon name="Model Book" /></TabsContent>
        <TabsContent value="weekly"><ComingSoon name="Weekly Synthesis" /></TabsContent>
      </Tabs>
    </div>
  )
}
