'use client'

import { useEffect, useState } from 'react'
import { tradingApi, type PositionSummary } from '@/lib/api'

export default function OpenPositionsBanner() {
  const [positions, setPositions] = useState<PositionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [closing, setClosing] = useState<number | null>(null)

  const fetchPositions = async () => {
    try {
      setLoading(true)
      const data = await tradingApi.getPositions()
      setPositions(data.positions || data) // Handle both old and new format
      
      // Show notification if positions were auto-closed
      if (data.auto_closed && data.auto_closed.length > 0) {
        data.auto_closed.forEach((closed: any) => {
          console.log(`✅ Position ${closed.symbol} auto-closed: ${closed.reason}`)
        })
      }
    } catch (e) {
      console.error('Failed to fetch positions', e)
    } finally {
      setLoading(false)
    }
  }

  const handleClose = async (positionId: number) => {
    if (closing === positionId) return // Prevent double-click
    
    try {
      setClosing(positionId)
      await tradingApi.closeTrade(positionId)
      // Refresh positions after close
      await fetchPositions()
    } catch (e: any) {
      console.error('Failed to close position', e)
      alert(`Failed to close position: ${e.message || 'Unknown error'}`)
    } finally {
      setClosing(null)
    }
  }

  useEffect(() => {
    fetchPositions()
    // Real-time updates: poll every 3 seconds for TP/SL checking
    const id = setInterval(fetchPositions, 3000)
    return () => clearInterval(id)
  }, [])

  if (loading && positions.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 text-xs text-slate-400">
        Loading positions...
      </div>
    )
  }

  if (positions.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 text-xs text-slate-500">
        No open positions.
      </div>
    )
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xs font-semibold text-white uppercase tracking-wide">Open Positions</h2>
        <button
          onClick={fetchPositions}
          className="text-[10px] px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded"
        >
          ↻ Refresh
        </button>
      </div>

      <table className="min-w-full text-[10px] text-slate-300">
        <thead className="border-b border-slate-800 text-[9px] uppercase text-slate-500">
          <tr>
            <th className="py-1 pr-2 text-left">Symbol</th>
            <th className="py-1 pr-2 text-right">Size</th>
            <th className="py-1 pr-2 text-right">Entry</th>
            <th className="py-1 pr-2 text-right">Mark</th>
            <th className="py-1 pr-2 text-right">Stop Loss</th>
            <th className="py-1 pr-2 text-right">Take Profit</th>
            <th className="py-1 pr-2 text-right">Margin</th>
            <th className="py-1 pr-2 text-right">PNL (ROI%)</th>
            <th className="py-1 pr-2 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.id} className="border-b border-slate-900/80 hover:bg-slate-800/30">
              <td className="py-1 pr-2">
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-1">
                  <span className="font-semibold text-xs text-white">{p.symbol}</span>
                    {p.ai_confidence && (
                      <span className="text-[8px] px-1 py-0.5 bg-purple-900/50 text-purple-300 rounded border border-purple-700">
                        🤖 Robot
                      </span>
                    )}
                  </div>
                  {p.trading_mode && (
                    <span className="text-[8px] text-slate-500 capitalize">{p.trading_mode}</span>
                  )}
                  <span className="text-[9px] text-slate-500">{p.side}</span>
                </div>
              </td>
              <td className="py-1 pr-2 text-right">{p.size}</td>
              <td className="py-1 pr-2 text-right">${p.entry_price.toFixed(2)}</td>
              <td className="py-1 pr-2 text-right">${p.mark_price.toFixed(2)}</td>
              <td className="py-1 pr-2 text-right">
                {p.stop_loss ? (
                  <span className="text-red-400">${p.stop_loss.toFixed(2)}</span>
                ) : (
                  <span className="text-slate-600">-</span>
                )}
              </td>
              <td className="py-1 pr-2 text-right">
                {p.take_profit ? (
                  <span className="text-green-400">${p.take_profit.toFixed(2)}</span>
                ) : (
                  <span className="text-slate-600">-</span>
                )}
              </td>
              <td className="py-1 pr-2 text-right">${p.margin.toFixed(2)}</td>
              <td className="py-1 pr-2 text-right">
                <span className={p.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                  ${p.pnl.toFixed(2)} ({p.roi_percent.toFixed(2)}%)
                </span>
              </td>
              <td className="py-1 pr-2 text-right">
                <button
                  onClick={() => handleClose(p.id)}
                  disabled={closing === p.id}
                  className="px-2 py-0.5 text-[9px] bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:opacity-50 text-white rounded transition-colors"
                >
                  {closing === p.id ? 'Closing...' : 'Close'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


