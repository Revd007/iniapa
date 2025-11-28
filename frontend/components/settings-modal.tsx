'use client'

import { useState, useEffect } from 'react'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

interface PortfolioMarginInfo {
  total_wallet_balance: number
  total_unrealized_pnl: number
  available_balance: number
  total_initial_margin: number
  total_maint_margin: number
  active_positions_count: number
  total_unrealized_profit: number
  assets?: Array<{
    asset: string
    crossWalletBalance: string
    crossUnPnl: string
    maintMargin: string
    initialMargin: string
  }>
  positions?: Array<{
    symbol: string
    positionAmt: string
    unrealizedProfit: string
    leverage: string
    entryPrice: string
  }>
}

interface AccountInfo {
  success: boolean
  environment: string
  has_custom_keys: boolean
  balance: number
  account_type?: string
  can_trade?: boolean
  can_withdraw?: boolean
  can_deposit?: boolean
  permissions?: string[]
  has_portfolio_margin?: boolean
  portfolio_margin?: PortfolioMarginInfo
  error?: string
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [environment, setEnvironment] = useState<'demo' | 'live'>('live')  // Default to 'live' for Futures trading
  const [loading, setLoading] = useState(false)
  const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    if (isOpen) {
      fetchAccountInfo()
      fetchCurrentSettings()
    }
  }, [isOpen, environment])

  const fetchAccountInfo = async () => {
    try {
      const response = await fetch(`http://localhost:8743/api/settings/account-info?env=${environment}`)
      const data = await response.json()
      setAccountInfo(data)
    } catch (error) {
      console.error('Failed to fetch account info:', error)
    }
  }

  const fetchCurrentSettings = async () => {
    try {
      const response = await fetch('http://localhost:8743/api/settings/current')
      const data = await response.json()
      if (data.success && data.has_custom_keys) {
        setEnvironment(data.environment as 'demo' | 'live')
      }
    } catch (error) {
      console.error('Failed to fetch current settings:', error)
    }
  }

  const handleSave = async () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      setMessage({ type: 'error', text: 'Please enter both API Key and Secret' })
      return
    }

    setLoading(true)
    setMessage(null)

    try {
      const response = await fetch('http://localhost:8743/api/settings/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          binance_api_key: apiKey,
          binance_api_secret: apiSecret,
          environment: environment
        })
      })

      const data = await response.json()

      if (data.success) {
        setMessage({ type: 'success', text: 'API keys saved successfully!' })
        setApiKey('')
        setApiSecret('')
        setTimeout(() => {
          fetchAccountInfo()
          // Auto-close modal after 1.5 seconds
          setTimeout(() => {
            onClose()
          }, 1500)
        }, 1000)
      } else {
        setMessage({ type: 'error', text: data.message || 'Failed to save API keys' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save API keys' })
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveKeys = async () => {
    if (!confirm('Remove your custom API keys and use default keys?')) return

    setLoading(true)
    setMessage(null)

    try {
      const response = await fetch('http://localhost:8743/api/settings/api-keys', {
        method: 'DELETE'
      })

      const data = await response.json()

      if (data.success) {
        setMessage({ type: 'success', text: 'Reverted to default API keys' })
        setApiKey('')
        setApiSecret('')
        setTimeout(() => {
          fetchAccountInfo()
          // Auto-close modal after 1.5 seconds
          setTimeout(() => {
            onClose()
          }, 1500)
        }, 1000)
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to remove API keys' })
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div 
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div 
        className="bg-slate-900 rounded-lg border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white">⚙️ Settings</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white hover:bg-slate-800 rounded-full w-8 h-8 flex items-center justify-center text-2xl leading-none transition"
            title="Close"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Account Info Section */}
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <h3 className="text-sm font-semibold text-white mb-3">📊 Account Information</h3>
            
            {accountInfo ? (
              <div className="space-y-3 text-sm">
                {/* Basic Info */}
                <div className="space-y-2 pb-2 border-b border-slate-700">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Environment:</span>
                    <span className={`font-medium ${accountInfo.environment === 'live' ? 'text-red-400' : 'text-green-400'}`}>
                      {accountInfo.environment === 'live' ? '🔴 LIVE' : '🟢 DEMO (Testnet)'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">API Keys:</span>
                    <span className="text-white font-medium">
                      {accountInfo.has_custom_keys ? '✅ Custom' : '⚠️ Default (Shared)'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Spot Balance:</span>
                    <span className="text-white font-medium">
                      ${accountInfo.balance.toFixed(2)} USDT
                    </span>
                  </div>
                  {accountInfo.account_type && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Account Type:</span>
                      <span className="text-white">{accountInfo.account_type}</span>
                    </div>
                  )}
                  {accountInfo.can_trade !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Trading:</span>
                      <span className={accountInfo.can_trade ? 'text-green-400' : 'text-red-400'}>
                        {accountInfo.can_trade ? '✅ Enabled' : '❌ Disabled'}
                      </span>
                    </div>
                  )}
                  {accountInfo.can_withdraw !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Withdraw:</span>
                      <span className={accountInfo.can_withdraw ? 'text-green-400' : 'text-red-400'}>
                        {accountInfo.can_withdraw ? '✅ Allowed' : '❌ Restricted'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Portfolio Margin Info */}
                {accountInfo.has_portfolio_margin && accountInfo.portfolio_margin && (
                  <div className="space-y-2 pt-2">
                    <div className="text-xs font-semibold text-purple-400 mb-2">
                      💼 Portfolio Margin Account
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Total Wallet Balance:</span>
                      <span className={`font-semibold text-lg ${
                        accountInfo.portfolio_margin.total_wallet_balance >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${accountInfo.portfolio_margin.total_wallet_balance.toFixed(2)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Available Balance:</span>
                      <span className="text-white font-medium">
                        ${accountInfo.portfolio_margin.available_balance.toFixed(2)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Unrealized PnL:</span>
                      <span className={`font-medium ${
                        accountInfo.portfolio_margin.total_unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {accountInfo.portfolio_margin.total_unrealized_pnl >= 0 ? '+' : ''}
                        ${accountInfo.portfolio_margin.total_unrealized_pnl.toFixed(2)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Initial Margin Used:</span>
                      <span className="text-yellow-400">
                        ${accountInfo.portfolio_margin.total_initial_margin.toFixed(2)} USDT
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Maintenance Margin:</span>
                      <span className="text-orange-400">
                        ${accountInfo.portfolio_margin.total_maint_margin.toFixed(2)} USDT
                      </span>
                    </div>
                    {accountInfo.portfolio_margin.active_positions_count > 0 && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Active Positions:</span>
                          <span className="text-white font-medium">
                            {accountInfo.portfolio_margin.active_positions_count}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Total Unrealized Profit:</span>
                          <span className={`font-medium ${
                            accountInfo.portfolio_margin.total_unrealized_profit >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {accountInfo.portfolio_margin.total_unrealized_profit >= 0 ? '+' : ''}
                            ${accountInfo.portfolio_margin.total_unrealized_profit.toFixed(2)} USDT
                          </span>
                        </div>
                        {/* Show active positions */}
                        {accountInfo.portfolio_margin.positions && accountInfo.portfolio_margin.positions.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-slate-700">
                            <div className="text-xs font-semibold text-slate-300 mb-1">Open Positions:</div>
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                              {accountInfo.portfolio_margin.positions.map((pos, idx) => (
                                <div key={idx} className="text-xs bg-slate-900/50 p-2 rounded">
                                  <div className="flex justify-between">
                                    <span className="text-slate-300 font-medium">{pos.symbol}</span>
                                    <span className={`${
                                      parseFloat(pos.unrealizedProfit) >= 0 ? 'text-green-400' : 'text-red-400'
                                    }`}>
                                      {parseFloat(pos.unrealizedProfit) >= 0 ? '+' : ''}
                                      ${parseFloat(pos.unrealizedProfit).toFixed(2)}
                                    </span>
                                  </div>
                                  <div className="flex justify-between text-slate-400 mt-1">
                                    <span>Size: {parseFloat(pos.positionAmt).toFixed(4)}</span>
                                    <span>Entry: ${parseFloat(pos.entryPrice).toFixed(2)}</span>
                                    <span>Leverage: {pos.leverage}x</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {accountInfo.error && (
                  <div className="text-red-400 text-xs mt-2 pt-2 border-t border-slate-700">
                    ⚠️ {accountInfo.error}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-slate-400 text-sm">Loading account info...</div>
            )}
          </div>

          {/* Environment Toggle */}
          <div>
            <label className="block text-sm font-medium text-white mb-2">
              Environment
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setEnvironment('demo')}
                className={`flex-1 py-2 px-4 rounded text-sm font-medium transition ${
                  environment === 'demo'
                    ? 'bg-green-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                🟢 Demo (Testnet)
              </button>
              <button
                onClick={() => setEnvironment('live')}
                className={`flex-1 py-2 px-4 rounded text-sm font-medium transition ${
                  environment === 'live'
                    ? 'bg-red-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                🔴 Live (Real Money)
              </button>
            </div>
            {environment === 'live' && (
              <p className="text-xs text-red-400 mt-2">
                ⚠️ Warning: Live trading uses real money! Make sure you understand the risks.
              </p>
            )}
          </div>

          {/* API Keys Form */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white mb-2">
                Binance API Key
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your Binance API Key"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white mb-2">
                Binance API Secret
              </label>
              <input
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Enter your Binance API Secret"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="bg-blue-900/20 border border-blue-700 rounded p-3">
              <p className="text-xs text-blue-300 mb-2">
                <strong>ℹ️ How to get API keys:</strong>
              </p>
              <ol className="text-xs text-blue-200 space-y-1 ml-4 list-decimal">
                <li>Go to <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" rel="noopener noreferrer" className="underline">Binance API Management</a></li>
                <li>Create a new API key</li>
                <li>Enable "Futures"</li>
                <li>Enable "Enable Spot & Margin Trading"</li>
                <li>Copy API Key and Secret here</li>
                <li>For Testnet: Use <a href="https://testnet.binance.vision/" target="_blank" rel="noopener noreferrer" className="underline">testnet.binance.vision</a></li>
              </ol>
            </div>
          </div>

          {/* Message Display */}
          {message && (
            <div className={`p-3 rounded text-sm ${
              message.type === 'success' 
                ? 'bg-green-900/30 border border-green-700 text-green-300'
                : 'bg-red-900/30 border border-red-700 text-red-300'
            }`}>
              {message.text}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleSave}
              disabled={loading || !apiKey.trim() || !apiSecret.trim()}
              className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:text-slate-500 text-white py-2 px-4 rounded font-medium transition"
            >
              {loading ? 'Saving...' : '💾 Save API Keys'}
            </button>
            
            {accountInfo?.has_custom_keys && (
              <button
                onClick={handleRemoveKeys}
                disabled={loading}
                className="bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-white py-2 px-4 rounded font-medium transition"
              >
                🗑️ Remove Keys
              </button>
            )}
            
            <button
              onClick={onClose}
              className="bg-slate-700 hover:bg-slate-600 text-white py-2 px-4 rounded font-medium transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

