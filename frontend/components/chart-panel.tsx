'use client'

import { useEffect, useState } from 'react'
import { chartApi, type ChartData } from '@/lib/api'
import CandlestickChartWithIndicators from './candlestick-chart-with-indicators'

interface ChartPanelProps {
  mode: 'scalper' | 'normal' | 'aggressive' | 'longhold'
  assetClass: 'stocks' | 'forex' | 'crypto'
  symbol: string
}

export default function ChartPanel({ mode, assetClass, symbol }: ChartPanelProps) {
  const [chartData, setChartData] = useState<ChartData[]>([])
  const [loading, setLoading] = useState(true)
  const [interval, setInterval] = useState('1h')
  const [currentPrice, setCurrentPrice] = useState<number>(0)
  const [priceChange, setPriceChange] = useState<number>(0)
  const [chartType, setChartType] = useState<'candle' | 'line'>('candle')
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Interval options - TradingView style (lengkap)
  const getAllIntervals = () => {
    return ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w', '1M']
  }

  const getIntervalOptions = () => {
    switch (mode) {
      case 'scalper':
        return ['1m', '3m', '5m', '15m', '30m', '1h']
      case 'longhold':
        return ['4h', '12h', '1d', '3d', '1w', '1M']
      case 'aggressive':
        return ['5m', '15m', '30m', '1h', '2h', '4h']
      default:
        return ['15m', '30m', '1h', '2h', '4h', '1d']
    }
  }

  const intervalOptions = getIntervalOptions()

  // Calculate optimal limit - maximize data untuk analisis lebih baik
  // Binance API support up to 1000 candles per request
  const getOptimalLimit = (mode: string, interval: string): number => {
    // Parse interval to minutes
    const intervalToMinutes: Record<string, number> = {
      '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
      '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720,
      '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
    }
    
    const minutes = intervalToMinutes[interval] || 60

    // Scalper: Maximum data for short timeframes
    if (mode === 'scalper') {
      if (minutes <= 5) return 1000   // 1m=16h, 3m=50h, 5m=83h
      if (minutes <= 15) return 1000  // 15m=10 days
      if (minutes <= 60) return 1000  // 30m=20 days, 1h=41 days
      return 500                       // 2h+=longer periods
    }
    
    // Long Hold: Maximum historical data
    if (mode === 'longhold') {
      if (minutes <= 240) return 1000 // Up to 4h = 166 days
      if (minutes <= 1440) return 500 // 1d = 500 days
      if (minutes <= 10080) return 365 // 1w = 7 years
      return 120                       // 1M = 10 years
    }
    
    // Aggressive: Maximum data for pattern recognition
    if (mode === 'aggressive') {
      if (minutes <= 5) return 1000
      if (minutes <= 60) return 1000
      if (minutes <= 240) return 1000
      return 500
    }
    
    // Normal: Generous limits untuk comprehensive analysis
    if (minutes <= 15) return 1000    // 15m=10 days
    if (minutes <= 60) return 1000    // 1h=41 days
    if (minutes <= 240) return 1000   // 4h=166 days
    if (minutes <= 1440) return 500   // 1d=500 days
    return 365                         // 1w=7 years
  }

  useEffect(() => {
    // Reset interval when mode changes
    const options = getIntervalOptions()
    if (!options.includes(interval)) {
      setInterval(options[0])
    } else {
      fetchChartData()
    }
  }, [mode, symbol, interval, assetClass])

  const fetchChartData = async () => {
    // Stocks chart is under development; skip fetching.
    if (assetClass === 'stocks') {
      setChartData([])
      setLoading(false)
      return
    }

    setLoading(true)

    try {
      // Calculate optimal limit based on mode and timeframe
      // Following Binance/TradingView best practices
      const limit = getOptimalLimit(mode, interval)
      const asset: 'crypto' | 'forex' = assetClass === 'forex' ? 'forex' : 'crypto'
      const data = await chartApi.getChartData(symbol, interval, limit, asset)
      
      setChartData(data)

      // Calculate current price and change
      if (data.length > 0) {
        const latest = data[data.length - 1]
        const first = data[0]
        setCurrentPrice(latest.close)
        const change = ((latest.close - first.close) / first.close) * 100
        setPriceChange(change)
      }

      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch chart data:', error)
      setLoading(false)
    }
  }

  // Format chart data for display
  const formatChartData = () => {
    return chartData.map((d) => ({
      time: new Date(d.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      price: d.close,
      ma20: d.ma20,
      ma50: d.ma50,
      rsi: d.rsi,
      macd: d.macd,
      macd_signal: d.macd_signal,
      macd_histogram: d.macd_histogram,
    }))
  }

  const chartTitles = {
    crypto: `${symbol}/USD Chart`,
    stocks: 'SPY Chart',
    forex: `${symbol}/USD Chart`,
  }

  // Only stocks are under development now; crypto + forex both use full chart.
  if (assetClass === 'stocks') {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
          {chartTitles[assetClass]}
        </h2>
        <div className="text-center py-16 text-slate-400">
          <p className="mb-2">🚧 Under Development</p>
          <p className="text-xs">Charts for stocks coming soon!</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-slate-900/50 border border-slate-800 rounded-lg flex flex-col ${
      isFullscreen ? 'fixed inset-0 z-50 m-0 rounded-none h-screen' : 'h-full'
    }`}>
      <div className="flex justify-between items-center p-2 border-b border-slate-800 flex-shrink-0">
        <div>
          <h2 className="text-[11px] font-semibold text-white uppercase tracking-wide">{chartTitles[assetClass]}</h2>
        </div>
        <div className="flex gap-1">
          {/* Chart Type Selector */}
          <button
            onClick={() => setChartType(chartType === 'candle' ? 'line' : 'candle')}
            className="px-1.5 py-0.5 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition"
            title={`Switch to ${chartType === 'candle' ? 'line' : 'candlestick'} chart`}
          >
            {chartType === 'candle' ? '📊' : '📈'}
          </button>
          
          {/* Interval Selector */}
          {intervalOptions.map((tf) => (
            <button
              key={tf}
              onClick={() => setInterval(tf)}
              className={`px-1.5 py-0.5 text-[10px] rounded transition ${
                interval === tf
                  ? 'bg-blue-600 text-white font-semibold'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
              }`}
            >
              {tf.toUpperCase()}
            </button>
          ))}
          
          {/* Refresh Button */}
          <button
            onClick={fetchChartData}
            className="px-1.5 py-0.5 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition"
            title="Refresh chart"
          >
            ↻
          </button>
          
          {/* Fullscreen Toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="px-1.5 py-0.5 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition"
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? '⊟' : '⊞'}
          </button>
        </div>
      </div>

      {/* Chart Area - Takes Full Available Space */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-slate-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"></div>
              <p className="text-xs">Loading chart data...</p>
            </div>
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-400">
            <div className="text-center">
              <p className="text-xs mb-2">No chart data available</p>
              <button
                onClick={fetchChartData}
                className="text-xs px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <div className="h-full w-full bg-slate-950">
            {chartType === 'candle' ? (
              <CandlestickChartWithIndicators data={chartData} />
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-xs text-slate-400 text-center">Line chart view - Switch to candlestick for full analysis</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Info Bar - Super Compact */}
      <div className="p-1.5 border-t border-slate-800 bg-slate-900/80 flex-shrink-0">
        <div className="flex items-center gap-2 text-[10px] flex-wrap">
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Price:</span>
            <span className="text-white font-bold">${currentPrice.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">Chg:</span>
            <span className={`font-bold ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
            </span>
          </div>
          {chartData.length > 0 && chartData[chartData.length - 1]?.rsi && (
            <div className="flex items-center gap-1">
              <span className="text-slate-500">RSI:</span>
              <span className={`font-semibold ${
                (chartData[chartData.length - 1]?.rsi ?? 0) > 70 ? 'text-red-400' : 
                (chartData[chartData.length - 1]?.rsi ?? 0) < 30 ? 'text-green-400' : 'text-white'
              }`}>
                {chartData[chartData.length - 1]?.rsi?.toFixed(1)}
              </span>
            </div>
          )}
          {chartData[chartData.length - 1]?.macd_histogram !== undefined && (
            <div className="flex items-center gap-1">
              <span className="text-slate-500">MACD:</span>
              <span className={`font-semibold ${
                (chartData[chartData.length - 1]?.macd_histogram ?? 0) > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {chartData[chartData.length - 1]?.macd_histogram?.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
