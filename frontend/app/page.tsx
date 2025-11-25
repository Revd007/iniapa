'use client'

import { useState } from 'react'
import Header from '@/components/header'
import AssetSelector from '@/components/asset-selector'
import TradingModeSelector from '@/components/trading-mode-selector'
import MarketOverview from '@/components/market-overview'
import RobotTrading from '@/components/robot-trading'
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
  const [showLeftSidebar, setShowLeftSidebar] = useState(true)
  const [showRightSidebar, setShowRightSidebar] = useState(true)
  const [environment, setEnvironment] = useState<'demo' | 'live'>('demo')

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Header 
        assetClass={assetClass} 
        onEnvironmentChange={setEnvironment}
      />
      
      <div className="flex-1 flex flex-col gap-2 overflow-hidden">
        {/* Top Controls - Compact, Single Row */}
        <div className="px-2 pt-2 flex gap-2 items-center flex-wrap">
        <AssetSelector assetClass={assetClass} setAssetClass={setAssetClass} />
        <TradingModeSelector mode={tradingMode} setMode={setTradingMode} />
          
          {/* Sidebar toggles - visible on larger screens */}
          <div className="hidden lg:flex gap-1 ml-auto">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
              title="Toggle Market Panel"
            >
              {showLeftSidebar ? '◀ Market' : '▶ Market'}
            </button>
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
              title="Toggle Trade Panel"
            >
              {showRightSidebar ? 'Trade ▶' : '◀ Trade'}
            </button>
          </div>
        </div>

        {/* Main Trading Area - Responsive Grid Layout */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[auto_1fr_auto] gap-2 px-2 pb-2 min-h-0 overflow-hidden">
          {/* Left Sidebar - Market Overview + Robot Trading */}
          {showLeftSidebar && (
            <div className="lg:w-56 xl:w-64 flex flex-col gap-2 max-h-full overflow-y-auto transition-all duration-300">
            <MarketOverview 
              assetClass={assetClass} 
              onSymbolSelect={setSelectedSymbol}
            />
            <RobotTrading 
              mode={tradingMode}
              assetClass={assetClass}
              environment={environment}
            />
          </div>
          )}

          {/* Center - CHART AREA (Flexible Height) - Always visible */}
          <div className="flex flex-col min-h-0 relative">
            <ChartPanel 
              mode={tradingMode} 
              assetClass={assetClass}
              symbol={selectedSymbol}
            />
            
            {/* Mobile sidebar toggle buttons - overlay on chart */}
            <div className="lg:hidden absolute top-2 left-2 flex flex-col gap-1">
              <button
                onClick={() => setShowLeftSidebar(!showLeftSidebar)}
                className="w-8 h-8 flex items-center justify-center bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-300 rounded text-xs"
                title="Toggle Market Panel"
              >
                {showLeftSidebar ? '◀' : '▶'}
              </button>
            </div>
            <div className="lg:hidden absolute top-2 right-2 flex flex-col gap-1">
              <button
                onClick={() => setShowRightSidebar(!showRightSidebar)}
                className="w-8 h-8 flex items-center justify-center bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-300 rounded text-xs"
                title="Toggle Trade Panel"
              >
                {showRightSidebar ? '▶' : '◀'}
              </button>
            </div>
          </div>

          {/* Right Sidebar - Trade Execution & AI (Compact) */}
          {showRightSidebar && (
            <div className="lg:w-72 xl:w-80 flex flex-col gap-2 max-h-full overflow-y-auto transition-all duration-300">
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
          )}
        </div>

        {/* Mobile Sidebars - Overlay on small screens */}
        {/* Left Sidebar Overlay */}
        {showLeftSidebar && (
          <div className="lg:hidden fixed inset-0 z-50 flex">
            {/* Backdrop */}
            <div 
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              onClick={() => setShowLeftSidebar(false)}
            />
            {/* Sidebar content */}
            <div className="relative w-64 bg-slate-900 border-r border-slate-800 overflow-y-auto flex flex-col gap-2 p-2">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-semibold text-white">Market & Robot</h3>
                <button
                  onClick={() => setShowLeftSidebar(false)}
                  className="w-6 h-6 flex items-center justify-center hover:bg-slate-800 rounded text-slate-400"
                >
                  ✕
                </button>
              </div>
              <MarketOverview 
                assetClass={assetClass} 
                onSymbolSelect={setSelectedSymbol}
              />
              <RobotTrading 
                mode={tradingMode}
                assetClass={assetClass}
                environment={environment}
              />
            </div>
          </div>
        )}

        {/* Right Sidebar Overlay */}
        {showRightSidebar && (
          <div className="lg:hidden fixed inset-0 z-50 flex justify-end">
            {/* Backdrop */}
            <div 
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              onClick={() => setShowRightSidebar(false)}
            />
            {/* Sidebar content */}
            <div className="relative w-64 bg-slate-900 border-l border-slate-800 overflow-y-auto flex flex-col gap-2 p-2">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-semibold text-white">Trade & AI</h3>
                <button
                  onClick={() => setShowRightSidebar(false)}
                  className="w-6 h-6 flex items-center justify-center hover:bg-slate-800 rounded text-slate-400"
                >
                  ✕
                </button>
              </div>
            <TradeExecution 
              mode={tradingMode} 
              assetClass={assetClass}
              symbol={selectedSymbol}
              environment={environment}
            />
            <AIRecommendationsDual 
              mode={tradingMode} 
              assetClass={assetClass}
            />
          </div>
        </div>
        )}

        {/* Bottom - Positions + Performance + Trade History - Responsive */}
        <div className="px-2 pb-2 flex flex-col gap-2 max-h-[400px] overflow-hidden">
          {/* Row 1: Open Positions + Performance - Stack on mobile */}
          <div className="flex flex-col md:flex-row gap-2 max-h-[200px] min-h-0">
            <div className="flex-1 min-w-0 overflow-y-auto">
              <OpenPositionsBanner environment={environment} />
            </div>
            <div className="flex-1 min-w-0 overflow-y-auto">
              <PerformanceDashboard assetClass={assetClass} environment={environment} />
            </div>
          </div>
          {/* Row 2: Trade History - Full width */}
          <div className="flex-1 min-w-0 overflow-y-auto max-h-[200px]">
            <TradeHistory environment={environment} />
          </div>
        </div>
      </div>
    </div>
  )
}
