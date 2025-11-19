'use client'

import { useState } from 'react'
import Header from '@/components/header'
import AssetSelector from '@/components/asset-selector'
import TradingModeSelector from '@/components/trading-mode-selector'
import MarketOverview from '@/components/market-overview'
import ChartPanel from '@/components/chart-panel'
import AIRecommendationsDual from '@/components/ai-recommendations-dual'
import TradeExecution from '@/components/trade-execution'
import PerformanceDashboard from '@/components/performance-dashboard'
import OpenPositionsBanner from '@/components/open-positions'
import TradeHistory from '@/components/trade-history'

type AssetClass = 'stocks' | 'forex' | 'crypto'
type TradingMode = 'scalper' | 'normal' | 'aggressive' | 'longhold'

export default function Home() {
  const [assetClass, setAssetClass] = useState<AssetClass>('crypto')
  const [tradingMode, setTradingMode] = useState<TradingMode>('normal')
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC')

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Header assetClass={assetClass} />
      
      <div className="flex-1 flex flex-col gap-2 overflow-hidden">
        {/* Top Controls - Compact, Single Row */}
        <div className="px-2 pt-2 flex gap-2 items-center">
        <AssetSelector assetClass={assetClass} setAssetClass={setAssetClass} />
        <TradingModeSelector mode={tradingMode} setMode={setTradingMode} />
        </div>

        {/* Main Trading Area - Responsive Grid Layout */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[auto_1fr_auto] gap-2 px-2 pb-2 min-h-0 overflow-hidden">
          {/* Left Sidebar - Market Overview (Compact) */}
          <div className="lg:w-56 xl:w-64 flex flex-col max-h-full">
            <MarketOverview 
              assetClass={assetClass} 
              onSymbolSelect={setSelectedSymbol}
            />
          </div>

          {/* Center - CHART AREA (Flexible Height) */}
          <div className="flex flex-col min-h-0">
            <ChartPanel 
              mode={tradingMode} 
              assetClass={assetClass}
              symbol={selectedSymbol}
            />
          </div>

          {/* Right Sidebar - Trade Execution & AI (Compact) */}
          <div className="lg:w-72 xl:w-80 flex flex-col gap-2 max-h-full overflow-y-auto">
            <TradeExecution 
              mode={tradingMode} 
              assetClass={assetClass}
              symbol={selectedSymbol}
            />
            <AIRecommendationsDual 
              mode={tradingMode} 
              assetClass={assetClass}
            />
          </div>
        </div>

        {/* Bottom - Positions + Performance + Trade History */}
        <div className="px-2 pb-2 flex flex-col gap-2" style={{ maxHeight: '400px' }}>
          {/* Row 1: Open Positions + Performance */}
          <div className="flex flex-col lg:flex-row gap-2" style={{ maxHeight: '200px' }}>
            <div className="flex-1 min-w-0 overflow-y-auto">
              <OpenPositionsBanner />
            </div>
            <div className="flex-1 min-w-0 overflow-y-auto">
              <PerformanceDashboard assetClass={assetClass} />
            </div>
          </div>
          {/* Row 2: Trade History */}
          <div className="flex-1 min-w-0 overflow-y-auto" style={{ maxHeight: '200px' }}>
            <TradeHistory />
          </div>
        </div>
      </div>
    </div>
  )
}
