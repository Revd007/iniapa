'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Header from '@/components/header'

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

interface WithdrawalRecord {
  id: number
  asset: string
  amount: number
  address: string
  network?: string
  address_tag?: string
  name?: string
  status: string
  withdrawal_id?: string
  transaction_id?: string
  environment: string
  error_message?: string
  created_at: string
}

type MenuSection = 'account' | 'api-keys' | 'withdrawal' | 'history'

export default function SettingsPage() {
  const router = useRouter()
  const [activeSection, setActiveSection] = useState<MenuSection>('account')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [environment, setEnvironment] = useState<'demo' | 'live'>('demo')
  const [loading, setLoading] = useState(false)
  const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  
  // Withdrawal states
  const [withdrawAsset, setWithdrawAsset] = useState('USDT')
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [withdrawAddress, setWithdrawAddress] = useState('')
  const [withdrawNetwork, setWithdrawNetwork] = useState('')
  const [withdrawAddressTag, setWithdrawAddressTag] = useState('')
  const [withdrawName, setWithdrawName] = useState('')
  const [maxWithdrawAmount, setMaxWithdrawAmount] = useState<number | null>(null)
  const [loadingMaxWithdraw, setLoadingMaxWithdraw] = useState(false)
  const [withdrawing, setWithdrawing] = useState(false)
  const [withdrawalHistory, setWithdrawalHistory] = useState<WithdrawalRecord[]>([])
  const [loadingWithdrawalHistory, setLoadingWithdrawalHistory] = useState(false)

  useEffect(() => {
    // Only fetch on mount
    fetchCurrentSettings()
  }, [])

  useEffect(() => {
    // Fetch account info when environment changes
    fetchAccountInfo()
    if (activeSection === 'history') {
      fetchWithdrawalHistory()
    }
    // Reset withdrawal form when environment changes
    setMaxWithdrawAmount(null)
    setWithdrawAmount('')
  }, [environment, activeSection])

  useEffect(() => {
    if (activeSection === 'history') {
      fetchWithdrawalHistory()
    }
  }, [activeSection])

  const fetchWithdrawalHistory = async () => {
    setLoadingWithdrawalHistory(true)
    try {
      const response = await fetch(`http://localhost:8000/api/account/withdrawal-history?env=${environment}&limit=50`)
      const data = await response.json()
      if (data.success) {
        setWithdrawalHistory(data.withdrawals || [])
      }
    } catch (error) {
      console.error('Failed to fetch withdrawal history:', error)
    } finally {
      setLoadingWithdrawalHistory(false)
    }
  }

  const fetchAccountInfo = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/settings/account-info?env=${environment}`)
      const data = await response.json()
      setAccountInfo(data)
    } catch (error) {
      console.error('Failed to fetch account info:', error)
    }
  }

  const fetchCurrentSettings = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/settings/current')
      const data = await response.json()
      if (data.success) {
        // Set API keys from database
        setApiKey(data.api_key || '')
        setApiSecret(data.api_secret || '')
        // Set environment from database
        const dbEnv = data.environment || 'demo'
        setEnvironment(dbEnv as 'demo' | 'live')
      }
    } catch (error) {
      console.error('Failed to fetch current settings:', error)
    }
  }

  const handleSaveApiKeys = async () => {
    setLoading(true)
    setMessage(null)
    
    try {
      const response = await fetch('http://localhost:8000/api/settings/api-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          binance_api_key: apiKey,
          binance_api_secret: apiSecret,
          environment: environment,
        }),
      })

      const data = await response.json()

      if (data.success) {
        setMessage({ type: 'success', text: '✅ API keys saved successfully!' })
        await fetchAccountInfo()
      } else {
        setMessage({ type: 'error', text: `❌ Failed to save: ${data.error || 'Unknown error'}` })
      }
    } catch (error) {
      setMessage({ type: 'error', text: `❌ Error: ${error}` })
    } finally {
      setLoading(false)
    }
  }

  const fetchMaxWithdraw = async () => {
    if (!withdrawAsset.trim()) return
    
    setLoadingMaxWithdraw(true)
    try {
      const response = await fetch(
        `http://localhost:8000/api/account/max-withdraw?asset=${withdrawAsset}&env=${environment}`
      )
      const data = await response.json()
      
      if (data.success && data.max_amount !== undefined) {
        setMaxWithdrawAmount(data.max_amount)
        setWithdrawAmount(data.max_amount.toString())
      } else {
        setMessage({ type: 'error', text: `❌ Failed to get max amount: ${data.error || 'Unknown error'}` })
      }
    } catch (error) {
      setMessage({ type: 'error', text: `❌ Error fetching max amount: ${error}` })
    } finally {
      setLoadingMaxWithdraw(false)
    }
  }

  const handleWithdraw = async () => {
    // Validation
    if (!withdrawAsset.trim() || !withdrawAmount.trim() || !withdrawAddress.trim()) {
      setMessage({ type: 'error', text: '❌ Please fill in all required fields (Asset, Amount, Address)' })
      return
    }

    const amount = parseFloat(withdrawAmount)
    if (isNaN(amount) || amount <= 0) {
      setMessage({ type: 'error', text: '❌ Invalid amount' })
      return
    }

    // Confirm for live environment
    if (environment === 'live') {
      const confirmed = window.confirm(
        `⚠️ WARNING: You are about to withdraw ${amount} ${withdrawAsset} in LIVE environment.\n\n` +
        `This is a REAL transaction and cannot be reversed!\n\n` +
        `Address: ${withdrawAddress}\n` +
        `Network: ${withdrawNetwork || 'Default'}\n\n` +
        `Are you absolutely sure?`
      )
      if (!confirmed) return
    }

    setWithdrawing(true)
    setMessage(null)

    try {
      const response = await fetch(`http://localhost:8000/api/account/withdraw?env=${environment}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          asset: withdrawAsset,
          amount: amount,
          address: withdrawAddress,
          network: withdrawNetwork || undefined,
          address_tag: withdrawAddressTag || undefined,
          name: withdrawName || undefined,
        }),
      })

      const data = await response.json()

      if (data.success) {
        setMessage({ 
          type: 'success', 
          text: `✅ Withdrawal submitted successfully! ID: ${data.withdrawal_id || 'N/A'}` 
        })
        // Reset form
        setWithdrawAmount('')
        setWithdrawAddress('')
        setWithdrawNetwork('')
        setWithdrawAddressTag('')
        setWithdrawName('')
        setMaxWithdrawAmount(null)
        // Refresh account info and history
        await fetchAccountInfo()
        await fetchWithdrawalHistory()
      } else {
        setMessage({ 
          type: 'error', 
          text: `❌ Withdrawal failed: ${data.error || 'Unknown error'}` 
        })
      }
    } catch (error) {
      setMessage({ type: 'error', text: `❌ Error: ${error}` })
    } finally {
      setWithdrawing(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-green-500/20 text-green-400 border-green-500/50'
      case 'PENDING':
      case 'PROCESSING':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50'
      case 'FAILED':
      case 'CANCELLED':
        return 'bg-red-500/20 text-red-400 border-red-500/50'
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/50'
    }
  }

  const menuItems = [
    { id: 'account' as MenuSection, label: 'Account Overview', icon: '👤' },
    { id: 'api-keys' as MenuSection, label: 'API Configuration', icon: '🔑' },
    { id: 'withdrawal' as MenuSection, label: 'Withdraw Funds', icon: '💸' },
    { id: 'history' as MenuSection, label: 'Withdrawal History', icon: '📜' },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Header assetClass="crypto" />
      
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Page Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">⚙️ Settings</h1>
            <p className="text-slate-400">Manage your account, API keys, and withdrawals</p>
          </div>
          <button
            onClick={() => router.push('/')}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition flex items-center gap-2"
          >
            <span>←</span> Back to Home
          </button>
        </div>

        {/* Environment Toggle */}
        <div className="mb-6 flex justify-end">
          <div className="bg-slate-800/50 rounded-lg p-1 flex gap-1 border border-slate-700">
            <button
              onClick={() => setEnvironment('demo')}
              className={`px-6 py-2 rounded-md font-medium transition ${
                environment === 'demo'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              🧪 Demo
            </button>
            <button
              onClick={() => setEnvironment('live')}
              className={`px-6 py-2 rounded-md font-medium transition ${
                environment === 'live'
                  ? 'bg-red-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              🔴 Live
            </button>
          </div>
        </div>

        {/* Message Display */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg border ${
            message.type === 'success' 
              ? 'bg-green-900/20 border-green-700 text-green-300' 
              : 'bg-red-900/20 border-red-700 text-red-300'
          }`}>
            {message.text}
          </div>
        )}

        {/* Main Layout with Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4 sticky top-24">
              <nav className="space-y-2">
                {menuItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id)}
                    className={`w-full text-left px-4 py-3 rounded-lg transition flex items-center gap-3 ${
                      activeSection === item.id
                        ? 'bg-purple-600 text-white shadow-lg'
                        : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                    }`}
                  >
                    <span className="text-xl">{item.icon}</span>
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </nav>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3">
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
              
              {/* Account Overview Section */}
              {activeSection === 'account' && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-3xl">👤</span>
                    <div>
                      <h2 className="text-2xl font-bold text-white">Account Overview</h2>
                      <p className="text-slate-400">Your current account status and balance</p>
                    </div>
                  </div>

                  {accountInfo ? (
                    <>
                      {/* Account Status Cards */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-gradient-to-br from-blue-900/30 to-blue-800/20 rounded-xl p-4 border border-blue-700/50">
                          <div className="text-blue-400 text-sm font-medium mb-1">Environment</div>
                          <div className="text-2xl font-bold text-white capitalize">{accountInfo.environment}</div>
                        </div>
                        
                        <div className="bg-gradient-to-br from-green-900/30 to-green-800/20 rounded-xl p-4 border border-green-700/50">
                          <div className="text-green-400 text-sm font-medium mb-1">Balance (USDT)</div>
                          <div className="text-2xl font-bold text-white">${accountInfo.balance.toFixed(2)}</div>
                        </div>
                        
                        <div className="bg-gradient-to-br from-purple-900/30 to-purple-800/20 rounded-xl p-4 border border-purple-700/50">
                          <div className="text-purple-400 text-sm font-medium mb-1">Account Type</div>
                          <div className="text-2xl font-bold text-white">{accountInfo.account_type || 'Standard'}</div>
                        </div>
                      </div>

                      {/* Permissions */}
                      <div className="bg-slate-900/50 rounded-xl p-5 border border-slate-700">
                        <h3 className="text-lg font-semibold text-white mb-4">🔐 Account Permissions</h3>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                            accountInfo.can_trade ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                          }`}>
                            <span>{accountInfo.can_trade ? '✅' : '❌'}</span>
                            <span className="font-medium">Trading</span>
                          </div>
                          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                            accountInfo.can_withdraw ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                          }`}>
                            <span>{accountInfo.can_withdraw ? '✅' : '❌'}</span>
                            <span className="font-medium">Withdrawal</span>
                          </div>
                          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                            accountInfo.can_deposit ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                          }`}>
                            <span>{accountInfo.can_deposit ? '✅' : '❌'}</span>
                            <span className="font-medium">Deposit</span>
                          </div>
                        </div>
                      </div>

                      {/* Portfolio Margin Info */}
                      {accountInfo.has_portfolio_margin && accountInfo.portfolio_margin && (
                        <div className="bg-gradient-to-br from-amber-900/20 to-orange-900/20 rounded-xl p-5 border border-amber-700/50">
                          <h3 className="text-lg font-semibold text-amber-400 mb-4">📊 Portfolio Margin Details</h3>
                          
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Total Wallet Balance</div>
                              <div className="text-lg font-bold text-white">
                                ${accountInfo.portfolio_margin.total_wallet_balance.toFixed(2)}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Available Balance</div>
                              <div className="text-lg font-bold text-white">
                                ${accountInfo.portfolio_margin.available_balance.toFixed(2)}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Unrealized PnL</div>
                              <div className={`text-lg font-bold ${
                                accountInfo.portfolio_margin.total_unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                ${accountInfo.portfolio_margin.total_unrealized_pnl.toFixed(2)}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Active Positions</div>
                              <div className="text-lg font-bold text-white">
                                {accountInfo.portfolio_margin.active_positions_count}
                              </div>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Initial Margin</div>
                              <div className="text-sm font-semibold text-white">
                                ${accountInfo.portfolio_margin.total_initial_margin.toFixed(2)}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-amber-300/70 mb-1">Maintenance Margin</div>
                              <div className="text-sm font-semibold text-white">
                                ${accountInfo.portfolio_margin.total_maint_margin.toFixed(2)}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-12">
                      <div className="animate-spin text-4xl mb-4">⚙️</div>
                      <div className="text-slate-400">Loading account information...</div>
                    </div>
                  )}
                </div>
              )}

              {/* API Keys Section */}
              {activeSection === 'api-keys' && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-3xl">🔑</span>
                    <div>
                      <h2 className="text-2xl font-bold text-white">API Configuration</h2>
                      <p className="text-slate-400">Configure your Binance API credentials</p>
                    </div>
                  </div>

                  <div className="bg-blue-900/20 border border-blue-700 rounded-lg p-4 mb-6">
                    <div className="flex gap-3">
                      <span className="text-2xl">ℹ️</span>
                      <div className="text-sm text-blue-300">
                        <p className="font-semibold mb-2">📌 API Key yang Harus Dipakai:</p>
                        {environment === 'demo' ? (
                          <div className="space-y-2">
                            <p className="font-semibold text-yellow-300">🧪 Untuk DEMO (Testnet):</p>
                            <ol className="list-decimal list-inside space-y-1 ml-2">
                              <li>Kunjungi <a href="https://testnet.binance.vision" target="_blank" rel="noopener noreferrer" className="underline text-yellow-200">testnet.binance.vision</a></li>
                              <li>Login dengan akun testnet (atau buat baru)</li>
                              <li>Buat API Key di testnet dashboard</li>
                              <li>Masukkan API Key & Secret dari <strong>testnet</strong> di sini</li>
                            </ol>
                            <p className="text-xs text-blue-200 mt-2">✅ Testnet API keys hanya untuk testing, tidak ada uang real!</p>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <p className="font-semibold text-red-300">🔴 Untuk LIVE (Production):</p>
                            <ol className="list-decimal list-inside space-y-1 ml-2">
                              <li>Kunjungi <a href="https://www.binance.com" target="_blank" rel="noopener noreferrer" className="underline text-red-200">www.binance.com</a></li>
                              <li>Login ke akun Binance <strong>REAL</strong> Anda</li>
                              <li>Go to API Management → Create API Key</li>
                              <li><strong className="text-red-400">PENTING:</strong> Set IP Restriction ke <strong>Unrestricted</strong></li>
                              <li>Enable permissions: <strong>Enable Reading + Enable Futures</strong></li>
                              <li>Masukkan API Key & Secret dari <strong>Binance Production</strong> di sini</li>
                            </ol>
                            <p className="text-xs text-red-200 mt-2">⚠️ LIVE API keys untuk trading REAL dengan uang REAL!</p>
                          </div>
                        )}
                        <div className="mt-3 pt-3 border-t border-blue-600">
                          <p className="text-xs text-blue-200">
                            💡 <strong>Permissions Required:</strong>
                          </p>
                          <ul className="text-xs text-blue-200 mt-1 ml-4 space-y-1">
                            <li>✅ <code className="bg-blue-900/50 px-1 rounded">Enable Reading</code> (WAJIB)</li>
                            <li>✅ <code className="bg-blue-900/50 px-1 rounded">Enable Futures</code> (WAJIB)</li>
                            <li>✅ <code className="bg-blue-900/50 px-1 rounded">Enable Withdrawals</code> (optional)</li>
                            <li>⚠️ <strong>IP Restriction: Unrestricted</strong> atau whitelist IP Anda</li>
                          </ul>
                        </div>
                        <div className="mt-2 p-2 bg-yellow-900/30 rounded border border-yellow-700">
                          <p className="text-xs text-yellow-200">
                            🚨 <strong>Jika error "Invalid API-key":</strong> Cek IP restriction di Binance API Management → Edit API → Set ke "Unrestricted"
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-semibold text-white mb-2">
                        API Key
                      </label>
                      <input
                        type="text"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="Enter your Binance API Key"
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-white mb-2">
                        API Secret
                      </label>
                      <input
                        type="password"
                        value={apiSecret}
                        onChange={(e) => setApiSecret(e.target.value)}
                        placeholder="Enter your Binance API Secret"
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition"
                      />
                    </div>

                    <button
                      onClick={handleSaveApiKeys}
                      disabled={loading}
                      className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white py-3 px-6 rounded-lg font-semibold transition shadow-lg"
                    >
                      {loading ? 'Saving...' : '💾 Save API Keys'}
                    </button>
                  </div>
                </div>
              )}

              {/* Withdrawal Section */}
              {activeSection === 'withdrawal' && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-3xl">💸</span>
                    <div>
                      <h2 className="text-2xl font-bold text-white">Withdraw Funds</h2>
                      <p className="text-slate-400">Transfer your funds to an external wallet</p>
                    </div>
                  </div>

                  {environment === 'live' && (
                    <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
                      <div className="flex gap-3">
                        <span className="text-2xl">⚠️</span>
                        <div className="text-sm text-red-300">
                          <p className="font-semibold mb-1">You are in LIVE environment</p>
                          <p>Withdrawals are real and irreversible. Please double-check all information before proceeding.</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {!accountInfo?.can_withdraw && (
                    <div className="bg-orange-900/20 border border-orange-700 rounded-lg p-4">
                      <div className="flex gap-3">
                        <span className="text-2xl">🚫</span>
                        <div className="text-sm text-orange-300">
                          <p className="font-semibold">Withdrawal Restricted</p>
                          <p>Your account currently does not have withdrawal permissions. Please check your Binance account settings.</p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-semibold text-white mb-2">
                          Asset <span className="text-red-400">*</span>
                        </label>
                        <input
                          type="text"
                          value={withdrawAsset}
                          onChange={(e) => setWithdrawAsset(e.target.value.toUpperCase())}
                          placeholder="e.g., USDT, BTC, ETH"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-white mb-2">
                          Amount <span className="text-red-400">*</span>
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="number"
                            value={withdrawAmount}
                            onChange={(e) => setWithdrawAmount(e.target.value)}
                            placeholder="Amount to withdraw"
                            step="0.01"
                            className="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                          />
                          <button
                            onClick={fetchMaxWithdraw}
                            disabled={loadingMaxWithdraw || !withdrawAsset.trim()}
                            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-semibold transition"
                          >
                            {loadingMaxWithdraw ? '...' : 'Max'}
                          </button>
                        </div>
                        {maxWithdrawAmount !== null && (
                          <p className="text-xs text-slate-400 mt-1">
                            Max available: {maxWithdrawAmount.toFixed(8)} {withdrawAsset}
                          </p>
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-white mb-2">
                        Wallet Address <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={withdrawAddress}
                        onChange={(e) => setWithdrawAddress(e.target.value)}
                        placeholder="Destination wallet address"
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                      />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-semibold text-white mb-2">
                          Network (optional)
                        </label>
                        <input
                          type="text"
                          value={withdrawNetwork}
                          onChange={(e) => setWithdrawNetwork(e.target.value)}
                          placeholder="e.g., TRC20, ERC20"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-semibold text-white mb-2">
                          Address Tag (optional)
                        </label>
                        <input
                          type="text"
                          value={withdrawAddressTag}
                          onChange={(e) => setWithdrawAddressTag(e.target.value)}
                          placeholder="Memo/Tag if required"
                          className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-white mb-2">
                        Name (optional)
                      </label>
                      <input
                        type="text"
                        value={withdrawName}
                        onChange={(e) => setWithdrawName(e.target.value)}
                        placeholder="Description for this withdrawal"
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                      />
                    </div>

                    <button
                      onClick={handleWithdraw}
                      disabled={withdrawing || !withdrawAsset.trim() || !withdrawAmount.trim() || !withdrawAddress.trim() || !accountInfo?.can_withdraw}
                      className="w-full bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white py-3 px-6 rounded-lg font-semibold transition shadow-lg"
                    >
                      {withdrawing ? 'Processing Withdrawal...' : '💸 Withdraw Funds'}
                    </button>
                  </div>
                </div>
              )}

              {/* Withdrawal History Section */}
              {activeSection === 'history' && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <span className="text-3xl">📜</span>
                      <div>
                        <h2 className="text-2xl font-bold text-white">Withdrawal History</h2>
                        <p className="text-slate-400">Track your past withdrawals</p>
                      </div>
                    </div>
                    <button
                      onClick={fetchWithdrawalHistory}
                      disabled={loadingWithdrawalHistory}
                      className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition"
                    >
                      {loadingWithdrawalHistory ? '🔄 Refreshing...' : '🔄 Refresh'}
                    </button>
                  </div>

                  {loadingWithdrawalHistory ? (
                    <div className="text-center py-12">
                      <div className="animate-spin text-4xl mb-4">⚙️</div>
                      <div className="text-slate-400">Loading withdrawal history...</div>
                    </div>
                  ) : withdrawalHistory.length > 0 ? (
                    <div className="space-y-3">
                      {withdrawalHistory.map((record) => (
                        <div
                          key={record.id}
                          className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition"
                        >
                          <div className="flex justify-between items-start mb-3">
                            <div>
                              <div className="text-lg font-bold text-white">
                                {record.amount} {record.asset}
                              </div>
                              <div className="text-xs text-slate-400">
                                {new Date(record.created_at).toLocaleString()}
                              </div>
                            </div>
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(record.status)}`}>
                              {record.status}
                            </span>
                          </div>

                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                              <span className="text-slate-400">Address:</span>
                              <span className="text-white font-mono text-xs">
                                {record.address.slice(0, 12)}...{record.address.slice(-8)}
                              </span>
                            </div>
                            {record.network && (
                              <div className="flex justify-between">
                                <span className="text-slate-400">Network:</span>
                                <span className="text-white">{record.network}</span>
                              </div>
                            )}
                            {record.withdrawal_id && (
                              <div className="flex justify-between">
                                <span className="text-slate-400">Withdrawal ID:</span>
                                <span className="text-white font-mono text-xs">{record.withdrawal_id}</span>
                              </div>
                            )}
                            {record.transaction_id && (
                              <div className="flex justify-between">
                                <span className="text-slate-400">Transaction ID:</span>
                                <span className="text-white font-mono text-xs">{record.transaction_id}</span>
                              </div>
                            )}
                            {record.error_message && (
                              <div className="mt-2 p-2 bg-red-900/30 rounded border border-red-700">
                                <span className="text-red-400 text-xs">{record.error_message}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 bg-slate-900/30 rounded-lg border border-slate-700">
                      <span className="text-6xl mb-4 block">📭</span>
                      <div className="text-slate-400 text-lg">No withdrawal history found</div>
                      <div className="text-slate-500 text-sm mt-2">Your withdrawals will appear here</div>
                    </div>
                  )}
                </div>
              )}

            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
