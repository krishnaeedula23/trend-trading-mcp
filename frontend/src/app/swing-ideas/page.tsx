"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UniverseManager } from "@/components/swing/universe-manager"
import { IdeasList } from "@/components/swing/ideas-list"
import { MarketHealthBar } from "@/components/swing/market-health-bar"
import { ExitedList } from "@/components/swing/exited-list"
import { ModelBookGrid } from "@/components/swing/model-book-grid"
import { WeeklyList } from "@/components/swing/weekly-list"

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
          <TabsTrigger value="model-book">Model Book</TabsTrigger>
          <TabsTrigger value="weekly">Weekly</TabsTrigger>
        </TabsList>

        <TabsContent value="active"><IdeasList status="active" /></TabsContent>
        <TabsContent value="watching"><IdeasList status="watching" /></TabsContent>
        <TabsContent value="exited"><ExitedList /></TabsContent>
        <TabsContent value="universe"><UniverseManager /></TabsContent>
        <TabsContent value="model-book"><ModelBookGrid /></TabsContent>
        <TabsContent value="weekly"><WeeklyList /></TabsContent>
      </Tabs>
    </div>
  )
}
