'use client'

import { useState, useEffect } from 'react'
import { aiApi, tradingApi, robotApi, type RobotConfig as ApiRobotConfig } from '@/lib/api'

interface RobotTradingProps {
  mode: 'scalper' | 'normal' | 'aggressive' | 'longhold'
  assetClass: 'stocks' | 'forex' | 'crypto'
  environment?: 'demo' | 'live'
}

/**
 * Robot Trading Component
 * 
 * Manages automated trading based on AI recommendations with configurable parameters:
 * - Confidence threshold: Minimum AI confidence to execute trades
 * - Leverage: Trading leverage (25x-50x)
 * - Capital per trade: Amount to allocate per position
 * - Max positions: Maximum concurrent positions
 * - Strategies: Active trading strategies
 * 
 * Configuration is stored in backend database and synced across sessions
 */

interface RobotConfig {
  enabled: boolean
  minConfidence: number
  maxPositions: number
  leverage: number
  strategies: string[]
  capitalPerTrade: number
}

// Default config for initial render (SSR compatibility)
const DEFAULT_CONFIG: RobotConfig = {
  enabled: false,
  minConfidence: 75,
  maxPositions: 3,
  leverage: 25,
  strategies: ['Breakout', 'Trend Fusion'],
  capitalPerTrade: 5,
}

export default function RobotTrading({ mode, assetClass, environment = 'demo' }: RobotTradingProps) {
  // State management
  const [config, setConfigState] = useState<RobotConfig>(DEFAULT_CONFIG)
  const [mounted, setMounted] = useState(false)
  const [status, setStatus] = useState<'idle' | 'scanning' | 'executing'>('idle')
  const [lastSignal, setLastSignal] = useState<any>(null)
  const [executedToday, setExecutedToday] = useState(0)
  const [loading, setLoading] = useState(false)
  
  /**
   * Load robot configuration from backend on mount
   * Syncs configuration from database to ensure consistency across sessions
   */
  useEffect(() => {
    setMounted(true)
    loadConfigFromBackend()
  }, [])

  /**
   * Load configuration from backend API
   * Automatically syncs with current mode and asset class
   */
  const loadConfigFromBackend = async () => {
    try {
      const apiConfig = await robotApi.getConfig()
      setConfigState({
        enabled: apiConfig.enabled,
        minConfidence: apiConfig.min_confidence,
        maxPositions: apiConfig.max_positions,
        leverage: apiConfig.leverage,
        strategies: apiConfig.strategies || [],
        capitalPerTrade: apiConfig.capital_per_trade,
      })
      setExecutedToday(apiConfig.total_trades_executed || 0)
    } catch (error) {
      console.error('Failed to load robot config from backend:', error)
      // Use default config if backend fails
    }
  }
  
  /**
   * Reload config when mode or asset class changes
   * Ensures robot follows current trading context
   */
  useEffect(() => {
    if (mounted) {
      // Update robot config with new mode/asset class
      const updateModeAndAsset = async () => {
        try {
          await robotApi.updateConfig({
            trading_mode: mode,
            asset_class: assetClass,
          })
        } catch (error) {
          console.error('Failed to update robot mode/asset:', error)
        }
      }
      updateModeAndAsset()
    }
  }, [mode, assetClass, mounted])

  /**
   * Stop robot when environment changes (demo <-> live)
   * Robot should never auto-start when switching environments
   */
  useEffect(() => {
    if (mounted && config.enabled) {
      // Stop robot when environment changes
      const stopRobot = async () => {
        try {
          await robotApi.stop(environment)
          setConfigState(prev => ({ ...prev, enabled: false }))
          await loadConfigFromBackend()
          console.log(`✅ Robot stopped due to environment change to ${environment}`)
        } catch (error) {
          console.error('Failed to stop robot on environment change:', error)
        }
      }
      stopRobot()
    }
  }, [environment, mounted])

  /**
   * Update configuration wrapper
   * Saves changes to backend API and updates local state
   */
  const setConfig = async (newConfig: RobotConfig | ((prev: RobotConfig) => RobotConfig)) => {
    const updated = typeof newConfig === 'function' ? newConfig(config) : newConfig
    setConfigState(updated)
    
    // Save to backend
    try {
      await robotApi.updateConfig({
        enabled: updated.enabled,
        min_confidence: updated.minConfidence,
        max_positions: updated.maxPositions,
        leverage: updated.leverage,
        strategies: updated.strategies,
        capital_per_trade: updated.capitalPerTrade,
        trading_mode: mode,
        asset_class: assetClass,
      })
    } catch (error) {
      console.error('Failed to save robot config to backend:', error)
    }
  }

  const strategies = [
    { id: 'Breakout', name: 'Breakout', desc: 'Price breaks resistance/support' },
    { id: 'Trend Fusion', name: 'Trend Fusion', desc: 'Multiple timeframe trend alignment' },
    { id: 'Counter Trend', name: 'Counter Trend', desc: 'Reversal at extremes' },
    { id: 'Fibonacci', name: 'Fibonacci', desc: 'Fib retracement levels' },
    { id: 'Mean Reversion', name: 'Mean Reversion', desc: 'Return to average' },
  ]

  /**
   * Scan for trading signals from AI recommendations
   * Fetches recommendations from configured AI models, filters by confidence,
   * and looks for consensus signals to execute
   */
  const scanForSignals = async () => {
    if (!config.enabled) return

    setStatus('scanning')
    try {
      // Trigger backend scan
      await robotApi.triggerScan()
      
      // Get recommendations from both AIs
      const [qwenRecs, deepseekRecs] = await Promise.all([
        aiApi.getRecommendations(mode, assetClass, 8, 'qwen'),
        aiApi.getRecommendations(mode, assetClass, 8, 'deepseek'),
      ])

      // Combine and filter by confidence threshold
      const allRecs = [...qwenRecs, ...deepseekRecs]
        .filter(r => !r.is_fallback && r.confidence >= config.minConfidence)
        .filter(r => ['STRONG BUY', 'BUY', 'STRONG SELL', 'SELL'].includes(r.signal))

      if (allRecs.length > 0) {
        // Find consensus (both AIs recommend same symbol)
        const symbolCounts = allRecs.reduce((acc: any, rec) => {
          acc[rec.symbol] = (acc[rec.symbol] || 0) + 1
          return acc
        }, {})

        const consensusSymbols = Object.entries(symbolCounts)
          .filter(([_, count]: [string, unknown]) => (count as number) >= 2)
          .map(([symbol]) => symbol)

        if (consensusSymbols.length > 0) {
          // Pick highest confidence from consensus
          const bestSignal = allRecs
            .filter(r => consensusSymbols.includes(r.symbol))
            .sort((a, b) => b.confidence - a.confidence)[0]

          setLastSignal(bestSignal)
          
          // Check if we should execute (within max positions limit)
          if (executedToday < config.maxPositions) {
            await executeRobotTrade(bestSignal)
          }
        }
      }
    } catch (e) {
      console.error('Robot scan error:', e)
    } finally {
      setStatus('idle')
    }
  }

  /**
   * Execute trade based on AI signal
   * 
   * Validates entry price, calculates quantity based on capital allocation,
   * ensures TP/SL are at safe distances, and executes the trade via trading API
   */
  const executeRobotTrade = async (signal: any) => {
    setStatus('executing')
    try {
      const side = ['STRONG BUY', 'BUY'].includes(signal.signal) ? 'BUY' : 'SELL'
      
      // Get entry price from signal (entry_price or entry range)
      const entryPrice = signal.entry_price || signal.entry || (signal.entry_range ? signal.entry_range.split('-')[0] : null)
      if (!entryPrice || entryPrice <= 0) {
        console.error('Invalid entry price from signal:', signal)
        return
      }
      
      // Calculate quantity based on capital per trade
      const quantity = config.capitalPerTrade / parseFloat(entryPrice)
      
      // Get TP/SL with validation
      const takeProfit = signal.target_price || signal.target || signal.take_profit
      const stopLoss = signal.stop_loss || signal.stop
      
      // Validate TP/SL distance (min 0.5% from entry)
      const minDistance = parseFloat(entryPrice) * 0.005 // 0.5%
      let validTP = takeProfit
      let validSL = stopLoss
      
      if (takeProfit) {
        const tpDistance = Math.abs(parseFloat(takeProfit) - parseFloat(entryPrice))
        if (tpDistance < minDistance) {
          // Set TP to 2% away from entry
          validTP = side === 'BUY' 
            ? parseFloat(entryPrice) * 1.02 
            : parseFloat(entryPrice) * 0.98
        }
      }
      
      if (stopLoss) {
        const slDistance = Math.abs(parseFloat(stopLoss) - parseFloat(entryPrice))
        if (slDistance < minDistance) {
          // Set SL to 1% away from entry
          validSL = side === 'BUY'
            ? parseFloat(entryPrice) * 0.99
            : parseFloat(entryPrice) * 1.01
        }
      }
      
      const result = await tradingApi.executeTrade({
        symbol: signal.symbol,
        side,
        quantity,
        order_type: 'MARKET',
        price: parseFloat(entryPrice),
        leverage: config.leverage,
        trading_mode: mode,
        stop_loss: validSL ? parseFloat(validSL) : undefined,
        take_profit: validTP ? parseFloat(validTP) : undefined,
        ai_confidence: signal.confidence,
        ai_reason: signal.reason,
      })

      if (result.success) {
        setExecutedToday(prev => prev + 1)
        console.log(`✅ Robot executed: ${side} ${signal.symbol} @ ${signal.entry_price}`)
      }
    } catch (e) {
      console.error('Robot execution error:', e)
    } finally {
      setStatus('idle')
    }
  }

  /**
   * Poll robot status periodically to ensure UI stays in sync with backend
   */
  useEffect(() => {
    if (!mounted) return
    
    const pollInterval = setInterval(() => {
      loadConfigFromBackend()
    }, 5000) // Poll every 5 seconds to keep UI in sync
    
    return () => clearInterval(pollInterval)
  }, [mounted])
  
  /**
   * Auto-scan interval when robot is enabled
   * Scans for signals every 30 seconds while robot is active
   */
  useEffect(() => {
    if (!config.enabled || !mounted) return

    // Scan every 30 seconds (configurable via backend in future)
    const interval = setInterval(() => {
      scanForSignals()
    }, 30000)

    // Initial scan on enable
    scanForSignals()

    return () => clearInterval(interval)
  }, [config.enabled, mode, assetClass, config.minConfidence, executedToday, mounted])

  return (
    <div className="bg-slate-900/95 backdrop-blur border border-slate-700 rounded-lg flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-2 border-b border-slate-700 flex items-center justify-between bg-gradient-to-r from-purple-900/20 to-blue-900/20 flex-shrink-0">
        <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold text-purple-400">🤖 ROBOT TRADING</span>
          <span className={`text-[9px] px-1.5 py-0.5 rounded ${
            config.enabled ? 'bg-green-900/30 text-green-400' : 'bg-slate-700 text-slate-400'
          }`}>
            {config.enabled ? '● ACTIVE' : '○ OFF'}
          </span>
          </div>
          <div className="text-[8px] text-slate-500">
            Mode: {mode.toUpperCase()} · {assetClass.toUpperCase()}
          </div>
        </div>
        <button
          onClick={async () => {
            setLoading(true)
            try {
              if (config.enabled) {
                // STOP robot
                const result = await robotApi.stop(environment)
                if (result.success) {
                  // Immediately update state for instant UI feedback
                  setConfigState(prev => ({ ...prev, enabled: false }))
                  // Reload config from backend to ensure sync
                  await loadConfigFromBackend()
                  console.log(`✅ Robot stopped (${environment} mode)`)
                } else {
                  console.error('Failed to stop robot:', result.message)
                  // Reload config anyway to sync with backend state
                  await loadConfigFromBackend()
                }
              } else {
                // START robot
                const result = await robotApi.start(environment)
                if (result.success) {
                  // Immediately update state for instant UI feedback
                  setConfigState(prev => ({ ...prev, enabled: true }))
                  // Reload config from backend to ensure sync
                  await loadConfigFromBackend()
                  console.log(`✅ Robot started (${environment} mode)`)
                } else {
                  console.error('Failed to start robot:', result.message)
                  // Reload config anyway to sync with backend state
                  await loadConfigFromBackend()
                }
              }
            } catch (error) {
              console.error('Failed to toggle robot:', error)
              // Reload config on error to sync with backend state
              await loadConfigFromBackend()
            } finally {
              setLoading(false)
            }
          }}
          disabled={loading}
          className={`px-2 py-0.5 text-[9px] font-bold rounded transition disabled:opacity-50 ${
            config.enabled 
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' 
              : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
          }`}
        >
          {loading ? '...' : config.enabled ? 'STOP' : 'START'}
        </button>
      </div>

      {/* Config */}
      <div className="p-2 space-y-1.5 flex-1 overflow-y-auto min-h-0">
        {/* Status */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <div className="text-[9px] text-slate-400 mb-1">Status</div>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-300">
              {status === 'scanning' && '🔍 Scanning signals...'}
              {status === 'executing' && '⚡ Executing trade...'}
              {status === 'idle' && config.enabled && '✓ Monitoring'}
              {status === 'idle' && !config.enabled && '⏸️ Paused'}
            </span>
            <span className="text-[9px] text-slate-500">
              {executedToday}/{config.maxPositions} today
            </span>
          </div>
        </div>

        {/* Confidence Threshold */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <label className="text-[9px] text-slate-400 block mb-1">
            Min Confidence: {config.minConfidence}%
          </label>
          <input
            type="range"
            min="50"
            max="95"
            step="5"
            value={config.minConfidence}
            onChange={(e) => setConfig(prev => ({ ...prev, minConfidence: parseInt(e.target.value) }))}
            className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
          />
          <div className="flex justify-between text-[8px] text-slate-500 mt-0.5">
            <span>50%</span>
            <span>95%</span>
          </div>
        </div>

        {/* Leverage */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <label className="text-[9px] text-slate-400 block mb-1">
            Leverage: {config.leverage}x 🔥
          </label>
          <div className="grid grid-cols-4 gap-1">
            {[25, 30, 40, 50].map(lev => (
              <button
                key={lev}
                onClick={() => setConfig(prev => ({ ...prev, leverage: lev }))}
                className={`px-1.5 py-1 text-[9px] font-bold rounded transition ${
                  config.leverage === lev
                    ? 'bg-orange-500/30 text-orange-300 border border-orange-500'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {lev}x
              </button>
            ))}
          </div>
        </div>

        {/* Capital per Trade - Flexible */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <div className="flex justify-between items-center mb-1">
            <label className="text-[9px] text-slate-400">
              Capital per Trade
          </label>
            <input
              type="number"
              min="1"
              max="100"
              step="0.5"
              value={config.capitalPerTrade}
              onChange={(e) => {
                const value = parseFloat(e.target.value) || 1
                setConfig(prev => ({ ...prev, capitalPerTrade: Math.min(100, Math.max(1, value)) }))
              }}
              className="w-16 px-1 py-0.5 text-[10px] text-center bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <input
            type="range"
            min="1"
            max="50"
            step="0.5"
            value={config.capitalPerTrade}
            onChange={(e) => setConfig(prev => ({ ...prev, capitalPerTrade: parseFloat(e.target.value) }))}
            className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
          <div className="flex justify-between text-[8px] text-slate-500 mt-0.5">
            <span>$1</span>
            <span>$50</span>
          </div>
          <div className="text-[8px] text-slate-500 mt-1">
            ⚠️ Adjust based on your account size
          </div>
        </div>

        {/* Max Positions */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <label className="text-[9px] text-slate-400 block mb-1">
            Max Positions: {config.maxPositions}
          </label>
          <div className="grid grid-cols-5 gap-1">
            {[1, 2, 3, 4, 5].map(max => (
              <button
                key={max}
                onClick={() => setConfig(prev => ({ ...prev, maxPositions: max }))}
                className={`px-1.5 py-1 text-[9px] font-bold rounded transition ${
                  config.maxPositions === max
                    ? 'bg-blue-500/30 text-blue-300 border border-blue-500'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {max}
              </button>
            ))}
          </div>
        </div>

        {/* Strategies */}
        <div className="bg-slate-800/50 p-1.5 rounded border border-slate-700">
          <div className="text-[9px] text-slate-400 mb-1">Strategies (Multi-select)</div>
          <div className="space-y-1">
            {strategies.map(strategy => (
              <button
                key={strategy.id}
                onClick={() => {
                  setConfig(prev => ({
                    ...prev,
                    strategies: prev.strategies.includes(strategy.id)
                      ? prev.strategies.filter(s => s !== strategy.id)
                      : [...prev.strategies, strategy.id]
                  }))
                }}
                className={`w-full text-left px-1.5 py-1 text-[9px] rounded transition ${
                  config.strategies.includes(strategy.id)
                    ? 'bg-purple-500/30 text-purple-300 border border-purple-500'
                    : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
                }`}
              >
                <div className="font-bold">{strategy.name}</div>
                <div className="text-[8px] opacity-70">{strategy.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Last Signal */}
        {lastSignal && (
          <div className="bg-gradient-to-br from-purple-900/20 to-blue-900/20 p-1.5 rounded border border-purple-700/50">
            <div className="text-[9px] text-purple-400 mb-1">📡 Last Signal</div>
            <div className="text-[10px] text-slate-200">
              <span className="font-bold">{lastSignal.symbol}</span>
              {' '}
              <span className={`px-1 py-0.5 rounded text-[8px] font-bold ${
                ['STRONG BUY', 'BUY'].includes(lastSignal.signal)
                  ? 'bg-green-500/30 text-green-300'
                  : 'bg-red-500/30 text-red-300'
              }`}>
                {lastSignal.signal}
              </span>
              {' '}
              <span className="text-slate-400">{lastSignal.confidence}%</span>
            </div>
            <div className="text-[8px] text-slate-400 mt-0.5">{lastSignal.reason}</div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-1.5 border-t border-slate-700 bg-slate-900/80 flex-shrink-0">
        <div className="text-[8px] text-slate-500 text-center">
          ⚠️ High Risk: {config.leverage}x leverage · ${config.capitalPerTrade}/trade
        </div>
        <div className="text-[7px] text-slate-600 text-center mt-0.5">
          Following {mode} mode recommendations
        </div>
      </div>
    </div>
  )
}

