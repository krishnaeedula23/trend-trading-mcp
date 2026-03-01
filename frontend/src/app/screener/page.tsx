"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { MomentumControls } from "@/components/screener/momentum-controls"
import { MomentumResultsTable } from "@/components/screener/momentum-results-table"
import { GoldenGateControls } from "@/components/screener/golden-gate-controls"
import { GoldenGateResultsTable } from "@/components/screener/golden-gate-results-table"
import { useMomentumScan } from "@/hooks/use-momentum-scan"
import { useGoldenGateScan } from "@/hooks/use-golden-gate-scan"
import { useWatchlists } from "@/hooks/use-watchlists"

function ComingSoon({ name }: { name: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-card/30 p-8 text-center">
      <p className="text-sm text-muted-foreground">{name} screener coming soon</p>
    </div>
  )
}

export default function ScreenerPage() {
  const momentum = useMomentumScan()
  const goldenGate = useGoldenGateScan()
  const { watchlists } = useWatchlists()

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
          <TabsTrigger value="golden-gate">Golden Gate</TabsTrigger>
          <TabsTrigger value="squeeze" disabled>
            Squeeze <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
          <TabsTrigger value="mean-reversion" disabled>
            Mean Reversion <Badge variant="outline" className="ml-1 text-[9px]">Soon</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="momentum" className="space-y-4">
          <MomentumControls
            scanning={momentum.scanning}
            response={momentum.response}
            error={momentum.error}
            watchlists={watchlists}
            initialUniverses={momentum.config.universes}
            initialMinPrice={momentum.config.min_price}
            onScan={momentum.runScan}
            onCancel={momentum.cancelScan}
          />
          <MomentumResultsTable hits={momentum.hits} />
        </TabsContent>

        <TabsContent value="golden-gate" className="space-y-4">
          <GoldenGateControls
            scanning={goldenGate.scanning}
            response={goldenGate.response}
            error={goldenGate.error}
            watchlists={watchlists}
            initialUniverses={goldenGate.config.universes}
            initialMinPrice={goldenGate.config.min_price}
            initialTradingMode={goldenGate.config.trading_mode}
            initialSignalType={goldenGate.config.signal_type}
            initialIncludePremarket={goldenGate.config.include_premarket}
            onScan={goldenGate.runScan}
            onCancel={goldenGate.cancelScan}
          />
          <GoldenGateResultsTable hits={goldenGate.hits} />
        </TabsContent>

        <TabsContent value="squeeze">
          <ComingSoon name="Squeeze" />
        </TabsContent>

        <TabsContent value="mean-reversion">
          <ComingSoon name="Mean Reversion" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
