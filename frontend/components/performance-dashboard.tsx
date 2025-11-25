'use client'

import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { performanceApi, type PerformanceMetrics } from '@/lib/api'

interface PerformanceDashboardProps {
  assetClass: 'stocks' | 'forex' | 'crypto'
  environment?: 'demo' | 'live'
}

export default function PerformanceDashboard({ assetClass, environment = 'demo' }: PerformanceDashboardProps) {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null)
  const [profitData, setProfitData] = useState<Array<{ day: string; profit: number }>>([])
  const [winRateData, setWinRateData] = useState<Array<{ name: string; value: number }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPerformanceData()
    
    // Real-time updates: poll every 5 seconds for live performance metrics
    const interval = setInterval(fetchPerformanceData, 5000)
    return () => clearInterval(interval)
  }, [assetClass, environment])

  const fetchPerformanceData = async () => {
    if (assetClass !== 'crypto') {
      setLoading(false)
      return
    }

    try {
      const data = await performanceApi.getDashboard(assetClass, environment)
      setMetrics(data.metrics)
      setProfitData(data.daily_profit)
      setWinRateData(data.win_rate_distribution)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch performance data:', error)
      setLoading(false)
    }
  }

  const COLORS = ['#10b981', '#ef4444']

  if (assetClass !== 'crypto') {
  return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
          Performance Dashboard
        </h2>
        <div className="text-center py-8 text-slate-400">
          <p className="mb-2">🚧 Under Development</p>
          <p className="text-xs">Performance tracking for {assetClass} coming soon!</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
          Performance Dashboard
        </h2>
        <div className="text-center py-8 text-slate-400">
          <div className="animate-spin w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full mx-auto mb-2"></div>
          <p className="text-xs">Loading performance data...</p>
        </div>
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
          Performance Dashboard
        </h2>
        <div className="text-center py-8 text-slate-400">
          <p className="text-xs mb-2">No performance data yet</p>
          <p className="text-xs text-slate-500">Execute some trades to see your performance metrics</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2">
        <div className="flex justify-between items-start mb-1">
          <p className="text-[10px] text-slate-400 uppercase tracking-wide">Total Profit</p>
          <button
            onClick={fetchPerformanceData}
            className="text-[10px] px-1 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded"
          >
            ↻
          </button>
        </div>
        <p className={`text-lg font-bold ${metrics.total_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          ${metrics.total_profit.toFixed(2)}
        </p>
        <p className={`text-[9px] mt-0.5 ${metrics.profit_percent >= 0 ? 'text-green-500' : 'text-red-500'}`}>
          {metrics.profit_percent >= 0 ? '+' : ''}{metrics.profit_percent}%
        </p>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2">
        <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">Win Rate</p>
        <p className="text-lg font-bold text-white">{metrics.win_rate}%</p>
        <p className="text-[9px] text-slate-500 mt-0.5">
          {metrics.winning_trades}W / {metrics.losing_trades}L
        </p>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2">
        <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">R/R Ratio</p>
        <p className="text-lg font-bold text-blue-400">{metrics.risk_reward_ratio}</p>
        <p className="text-[9px] text-slate-500 mt-0.5">Avg/trade</p>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-2">
        <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">Trades Today</p>
        <p className="text-lg font-bold text-purple-400">{metrics.trades_today}</p>
        <p className="text-[9px] text-slate-500 mt-0.5">{metrics.total_trades} total</p>
      </div>

      {profitData.length > 0 && (
        <div className="col-span-2 md:col-span-2 bg-slate-900/50 border border-slate-800 rounded-lg p-2">
          <h3 className="text-[10px] font-semibold text-white uppercase tracking-wide mb-2">Daily Profit</h3>
          <ResponsiveContainer width="100%" height={120}>
          <BarChart data={profitData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
            <XAxis dataKey="day" stroke="rgba(148, 163, 184, 0.5)" style={{ fontSize: '12px' }} />
            <YAxis stroke="rgba(148, 163, 184, 0.5)" style={{ fontSize: '12px' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(148, 163, 184, 0.2)' }}
                formatter={(value: any) => [`$${value}`, 'Profit']}
              />
              <Bar 
                dataKey="profit" 
                fill="#8b5cf6" 
                radius={[4, 4, 0, 0]}
              />
          </BarChart>
        </ResponsiveContainer>
      </div>
      )}

      {winRateData.length > 0 && (
        <div className="col-span-2 md:col-span-2 bg-slate-900/50 border border-slate-800 rounded-lg p-2 flex flex-col items-center">
          <h3 className="text-[10px] font-semibold text-white uppercase tracking-wide mb-2 w-full">Win Distribution</h3>
          <ResponsiveContainer width="100%" height={100}>
          <PieChart>
              <Pie 
                data={winRateData} 
                cx="50%" 
                cy="50%" 
                innerRadius={30} 
                outerRadius={40} 
                paddingAngle={2} 
                dataKey="value"
              >
              {winRateData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index]} />
              ))}
            </Pie>
              <Tooltip 
                contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(148, 163, 184, 0.2)' }}
              />
          </PieChart>
        </ResponsiveContainer>
          <div className="flex gap-2 text-[9px]">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500"></div>
              <span className="text-slate-400">W: {winRateData[0]?.value || 0}</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-red-500"></div>
              <span className="text-slate-400">L: {winRateData[1]?.value || 0}</span>
            </div>
          </div>
      </div>
      )}
    </div>
  )
}
