'use client'

import { useState } from 'react'
import { tradingApi, chartApi } from '@/lib/api'

interface TradeExecutionProps {
  mode: 'scalper' | 'normal' | 'aggressive' | 'longhold'
  assetClass: 'stocks' | 'forex' | 'crypto'
  symbol: string
  environment?: 'demo' | 'live'
}

export default function TradeExecution({ mode, assetClass, symbol, environment = 'demo' }: TradeExecutionProps) {
  const [tradeType, setTradeType] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState('0.01')
  const [entryPrice, setEntryPrice] = useState('')
  const [leverage, setLeverage] = useState('')
  const [speedMode, setSpeedMode] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const leverageMap = {
    scalper: '50',
    aggressive: '40',
    normal: '25',
    longhold: '10',
  }

  const speedMap = {
    scalper: 'ultra-fast',
    aggressive: 'fast',
    normal: 'standard',
    longhold: 'conservative',
  }

  const currentLeverage = leverage || leverageMap[mode]
  const currentSpeed = speedMode || speedMap[mode]

  const speedLabels = {
    'ultra-fast': 'Ultra-Fast',
    'fast': 'Fast',
    'standard': 'Standard',
    'conservative': 'Conservative',
  }

  const speedOptions = ['ultra-fast', 'fast', 'standard', 'conservative']

  const unitLabels = {
    crypto: symbol,
    stocks: 'Shares',
    forex: 'Lot',
  }

  // Fetch current price for the symbol
  const fetchCurrentPrice = async () => {
    try {
      const priceData = await chartApi.getRealtimePrice(symbol)
      setEntryPrice(priceData.price.toFixed(2))
    } catch (error) {
      console.error('Failed to fetch price:', error)
    }
  }

  // Execute trade
  const handleExecute = async () => {
    if (!quantity || parseFloat(quantity) <= 0) {
      setMessage({ type: 'error', text: 'Please enter a valid quantity' })
      return
    }

    setLoading(true)
    setMessage(null)

    try {
      // Get current price if not set
      let price = parseFloat(entryPrice)
      if (!price) {
        const priceData = await chartApi.getRealtimePrice(symbol)
        price = priceData.price
      }

      // Execute trade via API
      const result = await tradingApi.executeTrade({
        symbol: symbol,
        side: tradeType.toUpperCase(),
        quantity: parseFloat(quantity),
        order_type: 'MARKET',
        price: price,
        leverage: parseFloat(currentLeverage),
        trading_mode: mode,
        execution_mode: environment,
        stop_loss: stopLoss ? parseFloat(stopLoss) : undefined,
        take_profit: takeProfit ? parseFloat(takeProfit) : undefined,
      })

      if (result.success) {
        setMessage({ 
          type: 'success', 
          text: `${tradeType.toUpperCase()} order executed! ${quantity} ${symbol} @ $${price.toFixed(2)}` 
        })
        
        // Reset form after 3 seconds
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: result.message || 'Trade execution failed' })
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || 'Failed to execute trade' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg flex flex-col h-full">
      <div className="flex justify-between items-center p-3 border-b border-slate-800">
        <h2 className="text-xs font-semibold text-white uppercase tracking-wide">Quick Execute</h2>
        <button
          onClick={fetchCurrentPrice}
          className="text-xs px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded"
        >
          ↻
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
      <div className="flex gap-2">
        <button
          onClick={() => setTradeType('buy')}
            className={`flex-1 py-1.5 rounded text-sm font-bold transition ${
            tradeType === 'buy'
              ? 'bg-green-600 text-white'
              : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          BUY
        </button>
        <button
          onClick={() => setTradeType('sell')}
            className={`flex-1 py-1.5 rounded text-sm font-bold transition ${
            tradeType === 'sell'
              ? 'bg-red-600 text-white'
              : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          SELL
        </button>
      </div>

        <div className="space-y-2.5">
          {/* Symbol Display */}
          <div className="bg-purple-900/20 border border-purple-800/50 rounded px-2 py-1.5">
            <p className="text-[10px] text-purple-300">Symbol</p>
            <p className="text-white font-bold text-sm">{symbol}/USD</p>
          </div>

          {/* Quantity */}
        <div>
            <label className="block text-[10px] text-slate-400 mb-1">Quantity</label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-white text-xs focus:outline-none focus:border-purple-500"
              step="0.01"
              min="0.01"
          />
        </div>

          {/* Entry Price */}
        <div>
            <label className="block text-[10px] text-slate-400 mb-1">Entry Price</label>
          <input
            type="number"
            value={entryPrice}
            onChange={(e) => setEntryPrice(e.target.value)}
              placeholder="Market"
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-white text-xs focus:outline-none focus:border-purple-500"
            step="0.01"
          />
        </div>

          {/* Leverage */}
          <div className="grid grid-cols-2 gap-2">
        <div>
              <label className="block text-[10px] text-slate-400 mb-1">Leverage</label>
          <input
            type="number"
            value={leverage}
            onChange={(e) => setLeverage(e.target.value)}
            placeholder={leverageMap[mode]}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-white text-xs focus:outline-none focus:border-purple-500"
            min="1"
            max="20"
          />
        </div>
        <div>
              <label className="block text-[10px] text-slate-400 mb-1">Speed</label>
          <select
            value={speedMode}
            onChange={(e) => setSpeedMode(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-white text-xs focus:outline-none focus:border-purple-500"
          >
                <option value="">Default</option>
            {speedOptions.map((option) => (
              <option key={option} value={option}>
                {speedLabels[option as keyof typeof speedLabels]}
              </option>
            ))}
          </select>
        </div>
          </div>

          {/* SL/TP Section - Compact */}
          <div className="border-t border-slate-700 pt-2">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full text-[10px] text-slate-400 hover:text-white transition mb-2"
            >
              <span>🛡️ SL / TP</span>
              <span className="text-xs">{showAdvanced ? '▼' : '▶'}</span>
            </button>
            
            {showAdvanced && (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[9px] text-red-400 mb-1">Stop Loss</label>
                  <input
                    type="number"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    placeholder="$ SL"
                    className="w-full bg-slate-800 border border-red-900/50 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-red-500"
                    step="0.01"
                  />
                </div>
                <div>
                  <label className="block text-[9px] text-green-400 mb-1">Take Profit</label>
                  <input
                    type="number"
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(e.target.value)}
                    placeholder="$ TP"
                    className="w-full bg-slate-800 border border-green-900/50 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-green-500"
                    step="0.01"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {message && (
          <div className={`mx-3 p-2 rounded text-[10px] ${
            message.type === 'success' 
              ? 'bg-green-900/50 text-green-300 border border-green-800' 
              : 'bg-red-900/50 text-red-300 border border-red-800'
          }`}>
            {message.text}
          </div>
        )}
      </div>

      {/* Bottom Action Area */}
      <div className="p-3 border-t border-slate-800 space-y-2">
        <button 
          onClick={handleExecute}
          disabled={loading}
          className={`w-full py-2.5 rounded font-bold text-sm transition ${
            tradeType === 'buy'
              ? 'bg-green-600 hover:bg-green-700 text-white disabled:bg-green-900 disabled:cursor-not-allowed'
              : 'bg-red-600 hover:bg-red-700 text-white disabled:bg-red-900 disabled:cursor-not-allowed'
          }`}
        >
          {loading ? 'Executing...' : `Execute ${tradeType.toUpperCase()}`}
        </button>

        <div className="text-[9px] text-center text-slate-500">
          {stopLoss || takeProfit ? '🛡️ SL/TP enabled' : '⚠️ Add SL/TP for safety'}
        </div>
      </div>
    </div>
  )
}
