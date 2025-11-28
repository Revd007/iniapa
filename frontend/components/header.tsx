import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { accountApi, robotApi, type AccountSummary } from '@/lib/api';

interface HeaderProps {
  assetClass?: 'stocks' | 'forex' | 'crypto'
  onEnvironmentChange?: (env: 'demo' | 'live') => void
}

type EnvironmentType = 'demo' | 'live'

export default function Header({ assetClass, onEnvironmentChange }: HeaderProps) {
  const router = useRouter()
  const assetNames = {
    stocks: 'STOCKS',
    forex: 'FOREX',
    crypto: 'CRYPTO',
  }

  const displayAsset = assetClass && assetNames[assetClass]

  const [env, setEnv] = useState<EnvironmentType>('live')  // Default to 'live' for Futures trading
  const [balance, setBalance] = useState<number>(0)
  const [summary, setSummary] = useState<AccountSummary | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  const loadSummary = async (targetEnv?: EnvironmentType) => {
    try {
      const asset = assetClass === 'forex' ? 'forex' : 'crypto'
      const envToUse = targetEnv || env
      
      // Stop robot before switching environment
      try {
        await robotApi.stop(envToUse as 'demo' | 'live')
        console.log(`✅ Robot stopped before environment switch to ${envToUse}`)
      } catch (e) {
        console.warn('Failed to stop robot (may not be running):', e)
      }
      
      const data = await accountApi.getSummary(envToUse, asset)
      setSummary(data)
      const newEnv = data.environment || envToUse
      setEnv(newEnv)
      setBalance(data.equity || 0)
      
      // Notify parent component of environment change
      if (onEnvironmentChange) {
        onEnvironmentChange(newEnv)
      }
    } catch (e) {
      console.error('Failed to load account summary', e)
      setBalance(0)
      // Don't force env to demo on error
      if (onEnvironmentChange && !isInitialized) {
        onEnvironmentChange(env)
      }
    }
  }

  // Load saved environment from localStorage or API on mount
  useEffect(() => {
    const loadInitialEnv = async () => {
      try {
        // Try to get environment from settings API
        const response = await fetch('http://localhost:8743/api/settings/current')
        const data = await response.json()
        if (data.success && data.has_custom_keys) {
          const savedEnv = data.environment || 'demo'
          setEnv(savedEnv as EnvironmentType)
          await loadSummary(savedEnv as EnvironmentType)
        } else {
          await loadSummary('demo')
        }
      } catch (e) {
        await loadSummary('demo')
      }
      setIsInitialized(true)
    }
    loadInitialEnv()
  }, [assetClass])

  return (
    <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded bg-purple-600 flex items-center justify-center">
            <span className="text-white font-bold text-lg">T</span>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white truncate">ProTrade</h1>
              {displayAsset && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 uppercase">
                  {displayAsset}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500">Multi-asset trading workspace</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Environment toggle (Demo / Live) */}
          <div className="flex items-center text-[10px] bg-slate-800 rounded-full border border-slate-700 overflow-hidden">
            <button
              className={`px-3 py-1 ${env === 'demo' ? 'bg-emerald-500 text-black font-semibold' : 'text-slate-300'}`}
              onClick={() => loadSummary('demo')}
            >
              Demo
            </button>
            <button
              className={`px-3 py-1 border-l border-slate-700 ${env === 'live' ? 'bg-amber-500 text-black font-semibold' : 'text-slate-300'}`}
              onClick={() => loadSummary('live')}
            >
              Live
            </button>
          </div>

          {/* Balance summary */}
          <div className="hidden md:flex flex-col items-end">
            <p className="text-[11px] text-slate-400">
              Account Balance ({env === 'demo' ? 'Demo' : 'Live'})
            </p>
            {/* Use fixed en-US locale to avoid SSR/CSR mismatch like 0.00 vs 0,00 */}
            <p className="text-lg font-bold text-white">
              ${(balance ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>

          {/* Settings pill */}
          <button 
            onClick={() => router.push('/settings')}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-full text-xs font-medium border border-slate-700 transition"
          >
            ⚙️ Settings
          </button>
        </div>
      </div>
    </header>
  )
}
