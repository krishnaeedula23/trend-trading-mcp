"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { MomentumControls } from "@/components/screener/momentum-controls"
import { MomentumResultsTable } from "@/components/screener/momentum-results-table"
import { useMomentumScan } from "@/hooks/use-momentum-scan"

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-8 text-center">
      <p className="text-sm text-muted-foreground">{name} screener coming soon</p>
    </div>
  )
}

export default function ScreenerPage() {
  const { hits, scanning, response, config, runScan, cancelScan } = useMomentumScan()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Screener</h1>
        <p className="text-xs text-muted-foreground">
          Scan the market for momentum, squeeze, and setup opportunities
        </p>
      </div>

      <Tabs defaultValue="momentum" className="space-y-4">
        <TabsList>
          <TabsTrigger value="momentum">Momentum</TabsTrigger>
          <TabsTrigger value="squeeze" disabled>
            Squeeze <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
          <TabsTrigger value="golden-gate" disabled>
            Golden Gate <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
          <TabsTrigger value="mean-reversion" disabled>
            Mean Reversion <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="momentum" className="space-y-4">
          <MomentumControls
            scanning={scanning}
            response={response}
            initialUniverses={config.universes}
            initialMinPrice={config.min_price}
            onScan={runScan}
            onCancel={cancelScan}
          />
          <MomentumResultsTable hits={hits} />
        </TabsContent>

        <TabsContent value="squeeze">
          <ComingSoon name="Squeeze" />
        </TabsContent>

        <TabsContent value="golden-gate">
          <ComingSoon name="Golden Gate" />
        </TabsContent>

        <TabsContent value="mean-reversion">
          <ComingSoon name="Mean Reversion" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
