import React, { useEffect, useState } from 'react';
import { accountApi, type AccountSummary } from '@/lib/api';

interface HeaderProps {
  assetClass?: 'stocks' | 'forex' | 'crypto'
}

type EnvironmentType = 'demo' | 'live'

export default function Header({ assetClass }: HeaderProps) {
  const assetNames = {
    stocks: 'STOCKS',
    forex: 'FOREX',
    crypto: 'CRYPTO',
  }

  const displayAsset = assetClass && assetNames[assetClass]

  const [env, setEnv] = useState<EnvironmentType>('demo')
  const [balance, setBalance] = useState<number>(0)
  const [summary, setSummary] = useState<AccountSummary | null>(null)

  const loadSummary = async (targetEnv?: EnvironmentType) => {
    try {
      const asset = assetClass === 'forex' ? 'forex' : 'crypto'
      const data = await accountApi.getSummary(targetEnv, asset)
      setSummary(data)
      setEnv(data.environment)
      setBalance(data.equity)
    } catch (e) {
      console.error('Failed to load account summary', e)
    }
  }

  useEffect(() => {
    loadSummary()
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
              ${balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>

          {/* Settings pill */}
          <button className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-full text-xs font-medium border border-slate-700">
            Settings
          </button>
        </div>
      </div>
    </header>
  )
}
