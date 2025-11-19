'use client'

import { useEffect, useState } from 'react'
import { aiApi, type AIRecommendation } from '@/lib/api'

interface AIRecommendationsDualProps {
  mode: 'scalper' | 'normal' | 'aggressive' | 'longhold'
  assetClass: 'stocks' | 'forex' | 'crypto'
}

// Single AI Panel Component
interface AIPanelProps {
  model: 'deepseek' | 'qwen'
  mode: string
  assetClass: string
  recommendations: AIRecommendation[]
  loading: boolean
  error: string | null
  onRefresh: () => void
}

function AIPanel({ model, mode, assetClass, recommendations, loading, error, onRefresh }: AIPanelProps) {
  const modelName = model === 'deepseek' ? 'DeepSeek' : 'Qwen'
  const modelIcon = model === 'deepseek' ? '🚀' : '🧠'
  const modelColor = model === 'deepseek' ? 'bg-purple-900/50 text-purple-200' : 'bg-cyan-900/50 text-cyan-200'

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-slate-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs">{modelIcon}</span>
          <h3 className="text-[10px] font-semibold text-white uppercase tracking-wide">{modelName}</h3>
        </div>
        <div className="flex items-center gap-1">
          <span className={`text-[10px] px-1.5 py-0.5 ${modelColor} rounded capitalize`}>
            {mode}
          </span>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-xs px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded disabled:opacity-50"
          >
            {loading ? '...' : '↻'}
          </button>
        </div>
      </div>
      
      {/* Content */}
      {loading && recommendations.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 p-4">
          <div className="text-center">
            <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mx-auto mb-2"></div>
            <p className="text-xs">AI analyzing...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-red-400 p-4">
          <div className="text-center">
            <p className="text-xs mb-2">⚠️ {error}</p>
            <button
              onClick={onRefresh}
              className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded"
            >
              Retry
            </button>
          </div>
        </div>
      ) : recommendations.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 p-4">
          <p className="text-xs">No recommendations</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* CRITICAL WARNING: Show if any recommendations are fallback (not AI-generated) */}
          {recommendations.some(r => r.is_fallback) && (
            <div className="mx-2 mt-2 p-2 bg-red-900/50 border-2 border-red-600 rounded text-red-200">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-bold">⚠️ WARNING</span>
              </div>
              <p className="text-[10px] font-semibold">
                {modelName} AI unavailable. These are basic technical analysis only.
              </p>
              <p className="text-[9px] mt-1 opacity-80">
                DO NOT make trading decisions based on these. Wait for AI service to recover.
              </p>
            </div>
          )}
          <div className="p-2 space-y-1.5">
            {recommendations.map((rec, i) => (
              <div key={i} className={`border rounded p-2 ${rec.color} hover:opacity-90 transition-opacity cursor-pointer`}>
                {/* Header */}
                <div className="flex justify-between items-start mb-1">
                  <div className="flex-1">
                    <div className="font-bold text-xs">{rec.symbol}</div>
                    <div className="text-[9px] opacity-60">{rec.name}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-xs">{rec.signal}</div>
                    <div className="text-[9px] opacity-75">{rec.confidence}%</div>
                  </div>
                </div>

                {/* Confidence Bar */}
                <div className="w-full bg-black/30 rounded h-1 mb-1.5">
                  <div
                    className="h-1 rounded"
                    style={{
                      width: `${rec.confidence}%`,
                      backgroundColor: rec.signal.includes('BUY') ? '#10b981' : rec.signal.includes('SELL') ? '#ef4444' : '#f59e0b',
                    }}
                  />
                </div>

                {/* Reason - Compact */}
                <p className="text-[10px] opacity-75 mb-1.5 line-clamp-2">{rec.reason}</p>

                {/* Prices - Grid */}
                {(rec.entry_price || rec.target_price || rec.stop_loss) && (
                  <div className="grid grid-cols-3 gap-1 text-[9px] mb-1.5 opacity-75">
                    {rec.entry_price && <div><span className="opacity-60">E:</span> {rec.entry_price}</div>}
                    {rec.target_price && <div><span className="opacity-60">T:</span> {rec.target_price}</div>}
                    {rec.stop_loss && <div><span className="opacity-60">S:</span> {rec.stop_loss}</div>}
                  </div>
                )}

                {/* Meta - Compact */}
                <div className="flex justify-between items-center text-[9px] opacity-70 pt-1.5 border-t border-current/20">
                  <span>{rec.timeframe}</span>
                  <span>{rec.riskLevel}</span>
                  {rec.leverage && <span>{rec.leverage}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="text-[9px] opacity-50 p-2 border-t border-slate-700 bg-slate-900/80 flex-shrink-0">
        <div className="flex justify-between items-center">
          <span>{modelIcon} {modelName} AI</span>
          {!loading && recommendations.length > 0 && (
            recommendations.some(r => r.is_fallback) ? (
              <span className="text-red-400">⚠️ Fallback</span>
            ) : (
              <span className="text-green-400">● Live</span>
            )
          )}
        </div>
      </div>
    </div>
  )
}

// Main Dual Panel Component
export default function AIRecommendationsDual({ mode, assetClass }: AIRecommendationsDualProps) {
  // DeepSeek state
  const [deepseekRecs, setDeepseekRecs] = useState<AIRecommendation[]>([])
  const [deepseekLoading, setDeepseekLoading] = useState(true)
  const [deepseekError, setDeepseekError] = useState<string | null>(null)
  
  // Qwen state
  const [qwenRecs, setQwenRecs] = useState<AIRecommendation[]>([])
  const [qwenLoading, setQwenLoading] = useState(true)
  const [qwenError, setQwenError] = useState<string | null>(null)

  useEffect(() => {
    fetchBothRecommendations()
  }, [mode, assetClass])

  const fetchBothRecommendations = () => {
    fetchDeepseek()
    fetchQwen()
  }

  const fetchDeepseek = async () => {
    if (assetClass !== 'crypto') {
      setDeepseekRecs([])
      setDeepseekLoading(false)
      return
    }

    setDeepseekLoading(true)
    setDeepseekError(null)

    try {
      const data = await aiApi.getRecommendations(mode, assetClass, 6, 'deepseek')
      setDeepseekRecs(data)
      setDeepseekLoading(false)
    } catch (err: any) {
      setDeepseekError(err.message || 'Failed to fetch')
      setDeepseekLoading(false)
      console.error('DeepSeek error:', err)
    }
  }

  const fetchQwen = async () => {
    if (assetClass !== 'crypto') {
      setQwenRecs([])
      setQwenLoading(false)
      return
    }

    setQwenLoading(true)
    setQwenError(null)

    try {
      const data = await aiApi.getRecommendations(mode, assetClass, 6, 'qwen')
      setQwenRecs(data)
      setQwenLoading(false)
    } catch (err: any) {
      setQwenError(err.message || 'Failed to fetch')
      setQwenLoading(false)
      console.error('Qwen error:', err)
    }
  }

  if (assetClass !== 'crypto') {
    return (
      <div className="grid grid-cols-2 gap-4 h-full">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
            🚀 DeepSeek AI
          </h2>
          <div className="text-center py-8 text-slate-400">
            <p className="mb-2">🚧 Under Development</p>
            <p className="text-xs">AI recommendations for {assetClass} coming soon!</p>
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wide mb-3">
            🧠 Qwen AI
          </h2>
          <div className="text-center py-8 text-slate-400">
            <p className="mb-2">🚧 Under Development</p>
            <p className="text-xs">AI recommendations for {assetClass} coming soon!</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3 h-full">
      {/* Qwen Panel (LEFT) */}
      <AIPanel
        model="qwen"
        mode={mode}
        assetClass={assetClass}
        recommendations={qwenRecs}
        loading={qwenLoading}
        error={qwenError}
        onRefresh={fetchQwen}
      />
      
      {/* DeepSeek Panel (RIGHT) */}
      <AIPanel
        model="deepseek"
        mode={mode}
        assetClass={assetClass}
        recommendations={deepseekRecs}
        loading={deepseekLoading}
        error={deepseekError}
        onRefresh={fetchDeepseek}
      />
    </div>
  )
}

