'use client'

import { useEffect, useState } from 'react'
import { aiApi, userSettingsApi, type AIRecommendation } from '@/lib/api'

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

                {/* Entry/Target/SL Prices - CLEAR & VISIBLE (Top Priority) */}
                <div className="bg-slate-900/80 rounded p-2.5 mb-2 border border-slate-600/50">
                  <div className="grid grid-cols-3 gap-2.5">
                    {rec.entry_price && (
                      <div className="flex flex-col">
                        <span className="text-[9px] text-slate-400 mb-1 font-semibold uppercase">Entry</span>
                        <span className="text-blue-300 font-bold text-xs break-words">
                          {rec.entry_price.includes('$') ? rec.entry_price : `$${rec.entry_price}`}
                        </span>
                      </div>
                    )}
                    {rec.target_price && (
                      <div className="flex flex-col">
                        <span className="text-[9px] text-slate-400 mb-1 font-semibold uppercase">Target</span>
                        <span className="text-green-300 font-bold text-xs break-words">
                          {rec.target_price.includes('$') ? rec.target_price : `$${rec.target_price}`}
                        </span>
                      </div>
                    )}
                    {rec.stop_loss && (
                      <div className="flex flex-col">
                        <span className="text-[9px] text-slate-400 mb-1 font-semibold uppercase">Stop Loss</span>
                        <span className="text-red-300 font-bold text-xs break-words">
                          {rec.stop_loss.includes('$') ? rec.stop_loss : `$${rec.stop_loss}`}
                        </span>
                      </div>
                    )}
                  </div>
                  {!rec.entry_price && !rec.target_price && !rec.stop_loss && (
                    <div className="text-[9px] text-slate-500 text-center py-2">
                      No price data available. Wait for AI analysis...
                    </div>
                  )}
                </div>

                {/* Reason - CLEAR & FULL TEXT (No truncation) */}
                <div className="bg-slate-800/50 rounded p-2 mb-1.5 border border-slate-700/30">
                  <p className="text-[10px] text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                    {rec.reason || 'No analysis available'}
                  </p>
                </div>

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
            <>
              {recommendations.some(r => r.is_fallback) ? (
                <span className="text-red-400">⚠️ Fallback</span>
              ) : (
                <span className="text-green-400">● Live</span>
              )}
              {recommendations[0]?.provider_used && recommendations[0].provider_used !== 'legacy' && (
                <span className="text-blue-400 ml-2">
                  {recommendations[0].provider_used === 'openrouter' ? '☁️' : '💻'}
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// Main Dual Panel Component
export default function AIRecommendationsDual({ mode, assetClass }: AIRecommendationsDualProps) {
  // Qwen state only
  const [qwenRecs, setQwenRecs] = useState<AIRecommendation[]>([])
  const [qwenLoading, setQwenLoading] = useState(true)
  const [qwenError, setQwenError] = useState<string | null>(null)

  useEffect(() => {
    fetchBothRecommendations()
  }, [mode, assetClass])

  const fetchBothRecommendations = () => {
    // Only fetch Qwen
    fetchQwen()
  }

  // Helper: Get pinned symbols from DATABASE
  const getPinnedSymbols = async (): Promise<string[]> => {
    try {
      const symbols = await userSettingsApi.getPinnedSymbols(assetClass)
      console.log('[AI] Pinned symbols from DB:', symbols)
      return symbols
    } catch (e) {
      console.error('[AI] Failed to load pinned symbols from DB:', e)
      return []
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
      const pinnedSymbols = await getPinnedSymbols()
      console.log('[AI Qwen] Fetching with pinned symbols:', pinnedSymbols)
      const data = await aiApi.getRecommendations(mode, assetClass, 6, 'qwen', pinnedSymbols)
      console.log('[AI Qwen] Received recommendations:', data)
      setQwenRecs(data)
      setQwenLoading(false)
    } catch (err: any) {
      setQwenError(err.message || 'Failed to fetch')
      setQwenLoading(false)
      console.error('[AI Qwen] Error:', err)
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
    <div className="h-full">
      {/* Qwen Panel Only */}
      <AIPanel
        model="qwen"
        mode={mode}
        assetClass={assetClass}
        recommendations={qwenRecs}
        loading={qwenLoading}
        error={qwenError}
        onRefresh={fetchQwen}
      />
    </div>
  )
}

