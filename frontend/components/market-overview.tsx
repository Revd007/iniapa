'use client'

import { useEffect, useState } from 'react'
import { marketApi, CRYPTO_SYMBOLS, type MarketData } from '@/lib/api'

interface MarketOverviewProps {
  assetClass: 'stocks' | 'forex' | 'crypto'
  onSymbolSelect?: (symbol: string) => void
}

export default function MarketOverview({ assetClass, onSymbolSelect }: MarketOverviewProps) {
  const [markets, setMarkets] = useState<MarketData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC/USD')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [search, setSearch] = useState('')

  // Fetch market data
  const fetchMarketData = async () => {
    try {
      setError(null)
      const asset = assetClass === 'forex' ? 'forex' : 'crypto'
      const data = await marketApi.getOverview(asset)
      setMarkets(data)
      setLoading(false)
    } catch (err) {
      setError('Failed to fetch market data')
      setLoading(false)
      console.error('Market data error:', err)
    }
  }

  useEffect(() => {
    fetchMarketData()

    // Auto-refresh every 10 seconds if enabled
    if (autoRefresh) {
      const interval = setInterval(fetchMarketData, 10000)
      return () => clearInterval(interval)
    }
  }, [assetClass, autoRefresh])

  const handleSymbolClick = (symbol: string) => {
    setSelectedSymbol(symbol)
    if (onSymbolSelect) {
      onSymbolSelect(symbol.replace('/USD', ''))
    }
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg flex flex-col max-h-full">
      <div className="flex justify-between items-center p-2 border-b border-slate-800 flex-shrink-0">
        <h2 className="text-[10px] font-semibold text-white uppercase tracking-wide">
          {assetClass === 'forex' ? 'Forex' : 'Market'}
        </h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`text-[10px] px-1.5 py-0.5 rounded ${
              autoRefresh
                ? 'bg-green-900/50 text-green-400'
                : 'bg-slate-800 text-slate-400'
            }`}
            title="Auto-refresh"
          >
            {autoRefresh ? '●' : '○'}
          </button>
          <button
            onClick={fetchMarketData}
            className="text-xs px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:bg-slate-700"
          >
            ↻
          </button>
        </div>
      </div>

      {loading && markets.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 p-4">
          <div className="text-center">
            <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mx-auto mb-2"></div>
            <p className="text-xs">Loading...</p>
            </div>
            </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-red-400 p-4">
          <div className="text-center">
            <p className="text-xs mb-2">⚠️ {error}</p>
            <button
              onClick={fetchMarketData}
              className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded"
            >
              Retry
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-1.5 space-y-1 min-h-0">
          {/* Search input for symbols */}
          <div className="mb-1">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value.toUpperCase())}
              placeholder={assetClass === 'forex' ? 'Search pair (e.g. EURUSD, XAUUSD)' : 'Search symbol'}
              className="w-full px-2 py-1 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-purple-500"
            />
          </div>
          {markets
            .filter((m) => {
              if (!search) return true
              return m.symbol.toUpperCase().includes(search)
            })
            .map((m) => (
            <button
              key={m.symbol}
              onClick={() => handleSymbolClick(m.symbol)}
              className={`w-full text-left p-1.5 rounded transition ${
                selectedSymbol === m.symbol
                  ? 'bg-purple-900/40 border border-purple-600'
                  : 'bg-slate-800/30 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex justify-between items-center mb-0.5">
                <span className="font-semibold text-[11px] text-white">{m.symbol}</span>
                <span className={`text-[10px] font-medium ${parseFloat(m.change) < 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {m.change}
                </span>
              </div>
              <div className="flex justify-between items-center text-[10px]">
                <span className="text-slate-300 font-medium">${m.price}</span>
                <span className="text-slate-500 text-[9px]">{m.volume}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="text-[9px] opacity-50 p-1.5 border-t border-slate-700 bg-slate-900/80 flex-shrink-0">
        <div className="flex justify-between items-center">
          <span>Binance</span>
          {autoRefresh && <span className="text-green-400">● Live</span>}
        </div>
      </div>
    </div>
  )
}
