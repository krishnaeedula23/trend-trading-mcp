"use client"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UniverseManager } from "@/components/swing/universe-manager"

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

      <Tabs defaultValue="universe" className="space-y-4">
        <TabsList>
          <TabsTrigger value="active" disabled>Active <Badge variant="outline" className="ml-1 text-[9px]">Plan 2</Badge></TabsTrigger>
          <TabsTrigger value="watching" disabled>Watching <Badge variant="outline" className="ml-1 text-[9px]">Plan 2</Badge></TabsTrigger>
          <TabsTrigger value="exited" disabled>Exited <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
          <TabsTrigger value="universe">Universe</TabsTrigger>
          <TabsTrigger value="model-book" disabled>Model Book <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
          <TabsTrigger value="weekly" disabled>Weekly <Badge variant="outline" className="ml-1 text-[9px]">Plan 4</Badge></TabsTrigger>
        </TabsList>

        <TabsContent value="active"><ComingSoon name="Active ideas" /></TabsContent>
        <TabsContent value="watching"><ComingSoon name="Watching" /></TabsContent>
        <TabsContent value="exited"><ComingSoon name="Exited" /></TabsContent>
        <TabsContent value="universe"><UniverseManager /></TabsContent>
        <TabsContent value="model-book"><ComingSoon name="Model Book" /></TabsContent>
        <TabsContent value="weekly"><ComingSoon name="Weekly Synthesis" /></TabsContent>
      </Tabs>
    </div>
  )
}
