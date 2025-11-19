'use client'

import { useEffect, useState } from 'react'
import { tradingApi } from '@/lib/api'

interface Trade {
  id: number
  symbol: string
  side: string
  quantity: number
  entry_price: number
  exit_price: number | null
  profit_loss: number | null
  profit_loss_percent: number | null
  is_win: boolean | null
  status: string
  leverage: number
  trading_mode: string
  created_at: string
  closed_at: string | null
}

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)

  const fetchHistory = async () => {
    try {
      setLoading(true)
      const data = await tradingApi.getTradeHistory(100)
      setTrades(data)
    } catch (e) {
      console.error('Failed to fetch trade history', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory()
    // Refresh every 10 seconds
    const id = setInterval(fetchHistory, 10000)
    return () => clearInterval(id)
  }, [])

  if (loading && trades.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 text-xs text-slate-400">
        Loading trade history...
      </div>
    )
  }

  if (trades.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 text-xs text-slate-500">
        No trade history yet.
      </div>
    )
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xs font-semibold text-white uppercase tracking-wide">Trade History</h2>
        <button
          onClick={fetchHistory}
          className="text-[10px] px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
        >
          ↻ Refresh
        </button>
      </div>

      <table className="min-w-full text-[10px] text-slate-300">
        <thead className="border-b border-slate-800 text-[9px] uppercase text-slate-500">
          <tr>
            <th className="py-1 pr-2 text-left">Time</th>
            <th className="py-1 pr-2 text-left">Symbol</th>
            <th className="py-1 pr-2 text-right">Side</th>
            <th className="py-1 pr-2 text-right">Entry</th>
            <th className="py-1 pr-2 text-right">Exit</th>
            <th className="py-1 pr-2 text-right">Quantity</th>
            <th className="py-1 pr-2 text-right">Leverage</th>
            <th className="py-1 pr-2 text-right">P/L</th>
            <th className="py-1 pr-2 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => {
            const date = new Date(trade.created_at)
            const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            
            return (
              <tr key={trade.id} className="border-b border-slate-900/80 hover:bg-slate-800/30">
                <td className="py-1 pr-2">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-400">{dateStr}</span>
                    <span className="text-[9px] text-slate-500">{timeStr}</span>
                  </div>
                </td>
                <td className="py-1 pr-2 font-semibold text-xs text-white">{trade.symbol}</td>
                <td className="py-1 pr-2 text-right">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                    trade.side === 'BUY' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
                  }`}>
                    {trade.side}
                  </span>
                </td>
                <td className="py-1 pr-2 text-right">${trade.entry_price.toFixed(2)}</td>
                <td className="py-1 pr-2 text-right">
                  {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}
                </td>
                <td className="py-1 pr-2 text-right">{trade.quantity}</td>
                <td className="py-1 pr-2 text-right">{trade.leverage}x</td>
                <td className="py-1 pr-2 text-right">
                  {trade.profit_loss !== null ? (
                    <span className={trade.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}>
                      ${trade.profit_loss.toFixed(2)}
                      {trade.profit_loss_percent !== null && (
                        <span className="text-[9px] ml-1">
                          ({trade.profit_loss_percent >= 0 ? '+' : ''}{trade.profit_loss_percent.toFixed(2)}%)
                        </span>
                      )}
                    </span>
                  ) : (
                    <span className="text-slate-600">-</span>
                  )}
                </td>
                <td className="py-1 pr-2 text-right">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                    trade.status === 'CLOSED' 
                      ? trade.is_win 
                        ? 'bg-green-900/50 text-green-400' 
                        : 'bg-red-900/50 text-red-400'
                      : 'bg-blue-900/50 text-blue-400'
                  }`}>
                    {trade.status}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}


