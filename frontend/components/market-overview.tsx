'use client'

import { useEffect, useState } from 'react'
import { marketApi, userSettingsApi, CRYPTO_SYMBOLS, type MarketData } from '@/lib/api'

interface MarketOverviewProps {
  assetClass: 'stocks' | 'forex' | 'crypto'
  onSymbolSelect?: (symbol: string) => void
}

/**
 * Market Overview Component with Custom Symbol Management
 * 
 * Features:
 * - Pin up to 5 custom symbols
 * - Search and add symbols to pinned list
 * - Remove pinned symbols
 * - Falls back to top 5 if no symbols pinned
 * - Persistent storage using localStorage
 */

const STORAGE_KEY_PREFIX = 'market_pinned_symbols_'
const MAX_PINNED = 5

export default function MarketOverview({ assetClass, onSymbolSelect }: MarketOverviewProps) {
  const [allMarkets, setAllMarkets] = useState<MarketData[]>([])  // All symbols for search
  const [pinnedSymbols, setPinnedSymbols] = useState<string[]>([])  // User's pinned symbols (max 5)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC/USD')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [search, setSearch] = useState('')
  
  // Load pinned symbols from DATABASE on mount
  useEffect(() => {
    const loadPinnedSymbols = async () => {
      try {
        const symbols = await userSettingsApi.getPinnedSymbols(assetClass)
        console.log('[Market] Loaded pinned symbols from DB:', symbols)
        setPinnedSymbols(symbols)
      } catch (e) {
        console.error('[Market] Failed to load pinned symbols:', e)
      }
    }
    loadPinnedSymbols()
  }, [assetClass])
  
  // Save pinned symbols to DATABASE whenever they change
  useEffect(() => {
    const savePinnedSymbols = async () => {
      if (pinnedSymbols.length > 0) {
        try {
          await userSettingsApi.updatePinnedSymbols(assetClass, pinnedSymbols)
          console.log('[Market] Saved pinned symbols to DB:', pinnedSymbols)
        } catch (e) {
          console.error('[Market] Failed to save pinned symbols:', e)
        }
      }
    }
    // Only save if pinnedSymbols was actually changed by user (not initial load)
    if (pinnedSymbols.length > 0) {
      const timer = setTimeout(savePinnedSymbols, 500) // Debounce
      return () => clearTimeout(timer)
    }
  }, [pinnedSymbols, assetClass])
  
  // Calculate displayed markets based on search and pinned symbols
  const displayedMarkets = search.trim() 
    ? // When searching: show filtered results with pin status
      allMarkets.filter((m) => {
        const symbolUpper = m.symbol.toUpperCase()
        const searchUpper = search.toUpperCase().trim()
        const rawSymbol = (m as any).raw_symbol || m.symbol.replace('/USD', '').replace('/USDT', '').replace('USDT', '')
        
        return symbolUpper.includes(searchUpper) || 
               rawSymbol.toUpperCase().includes(searchUpper) ||
               symbolUpper.replace('/', '').includes(searchUpper) ||
               symbolUpper.replace('/USDT', '').replace('/USD', '').includes(searchUpper)
      })
    : // When not searching: show pinned symbols OR top 5 if no pins
      pinnedSymbols.length > 0
        ? allMarkets.filter(m => pinnedSymbols.includes(m.symbol))
        : allMarkets.slice(0, 5)
  
  // Toggle pin/unpin symbol
  const togglePin = (symbol: string) => {
    setPinnedSymbols(prev => {
      if (prev.includes(symbol)) {
        // Unpin
        return prev.filter(s => s !== symbol)
      } else {
        // Pin (max 5)
        if (prev.length >= MAX_PINNED) {
          // Replace oldest pinned symbol
          return [...prev.slice(1), symbol]
        }
        return [...prev, symbol]
      }
    })
  }
  
  // Check if symbol is pinned
  const isPinned = (symbol: string) => pinnedSymbols.includes(symbol)

  // Fetch market data
  const fetchMarketData = async () => {
    try {
      setError(null)
      const asset = assetClass === 'forex' ? 'forex' : 'crypto'
      const data = await marketApi.getOverview(asset)
      setAllMarkets(data)  // Simpan semua untuk search
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
      // Convert "BTC/USDT" -> "BTC" atau "ZECUSDT" -> "ZEC"
      // Hapus /USDT, /USD, dan USDT dari symbol untuk mendapatkan base asset
      let baseSymbol = symbol.replace('/USDT', '').replace('/USD', '')
      if (baseSymbol.endsWith('USDT')) {
        baseSymbol = baseSymbol.slice(0, -4) // Remove USDT suffix
      }
      onSymbolSelect(baseSymbol)
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

      {loading && allMarkets.length === 0 ? (
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
          <div className="mb-1 relative">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value.toUpperCase())}
              placeholder={assetClass === 'forex' ? 'Search pair (e.g. EURUSD, XAUUSD)' : 'Search (BCH, LTC, TURTLE...)'}
              className="w-full px-2 py-1 pr-6 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-purple-500"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-1 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs px-1"
                title="Clear search"
              >
                ×
              </button>
            )}
          </div>
          {!search && pinnedSymbols.length > 0 && (
            <div className="text-[9px] text-purple-400 mb-1 px-1 flex justify-between items-center">
              <span>📌 {pinnedSymbols.length}/{MAX_PINNED} pinned</span>
              {pinnedSymbols.length >= MAX_PINNED && (
                <span className="text-slate-500">Max reached</span>
              )}
            </div>
          )}
          {search && (
            <div className="text-[9px] text-purple-400 mb-1 px-1">
              Found {displayedMarkets.length} result{displayedMarkets.length !== 1 ? 's' : ''}
            </div>
          )}
          {displayedMarkets.length === 0 && search ? (
            <div className="text-center text-slate-500 text-[10px] py-4">
              No symbols found matching "{search}"
            </div>
          ) : (
            displayedMarkets.map((m) => {
              const pinned = isPinned(m.symbol)
              return (
                <div
              key={m.symbol}
                  className={`relative rounded transition ${
                selectedSymbol === m.symbol
                  ? 'bg-purple-900/40 border border-purple-600'
                  : 'bg-slate-800/30 hover:bg-slate-800/60'
              }`}
                >
                  <button
                    onClick={() => handleSymbolClick(m.symbol)}
                    className="w-full text-left p-1.5 pr-8"
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
                  
                  {/* Pin/Unpin button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      togglePin(m.symbol)
                    }}
                    className={`absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded transition ${
                      pinned
                        ? 'text-purple-400 hover:text-purple-300'
                        : 'text-slate-600 hover:text-slate-400'
                    }`}
                    title={pinned ? 'Unpin symbol' : `Pin symbol (${pinnedSymbols.length}/${MAX_PINNED})`}
                  >
                    {pinned ? '📌' : '📍'}
                  </button>
                </div>
              )
            })
          )}
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
