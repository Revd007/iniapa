'use client'

import { useState, useEffect } from 'react'

interface OpenRouterConfig {
  enabled: boolean
  api_key_set: boolean
  api_key_preview: string | null
  model: string
  status: string | null
  credits_remaining: number | null
  last_error: string | null
  requests_count: number
}

interface AgentRouterConfig {
  enabled: boolean
  api_key_set: boolean
  api_key_preview: string | null
  base_url: string
  model: string
  cli_installed: boolean
  cli_version: string | null
  status: string | null
  last_error: string | null
  requests_count: number
}

interface AIProviderConfig {
  active_provider: 'openrouter' | 'agentrouter'
  openrouter: OpenRouterConfig
  agentrouter: AgentRouterConfig
  auto_fallback: boolean
  fallback_order: string[]
}

interface ModelOption {
  id: string
  name: string
  description: string
  recommended?: boolean
}

export default function AIProviderSettings() {
  const [config, setConfig] = useState<AIProviderConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<{ provider: string } | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  
  // Form states
  const [activeProvider, setActiveProvider] = useState<'openrouter' | 'agentrouter'>('openrouter')
  const [openrouterApiKey, setOpenrouterApiKey] = useState('')
  const [openrouterModel, setOpenrouterModel] = useState('qwen/qwen3-max')
  const [openrouterEnabled, setOpenrouterEnabled] = useState(true)
  const [agentrouterApiKey, setAgentrouterApiKey] = useState('')
  const [agentrouterModel, setAgentrouterModel] = useState('qwen')
  const [agentrouterBaseUrl, setAgentrouterBaseUrl] = useState('http://localhost:3000')
  const [agentrouterEnabled, setAgentrouterEnabled] = useState(false)
  const [autoFallback, setAutoFallback] = useState(true)
  
  // Available models
  const [availableModels, setAvailableModels] = useState<{
    openrouter: ModelOption[]
    agentrouter: ModelOption[]
  }>({
    openrouter: [],
    agentrouter: []
  })
  
  // AgentRouter CLI status
  const [cliStatus, setCliStatus] = useState<{
    installed: boolean
    running: boolean
    version: string | null
  } | null>(null)

  useEffect(() => {
    loadConfig()
    loadAvailableModels()
  }, [])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8743'}/api/ai-providers/config`)
      const data = await response.json()
      
      if (data.success) {
        setConfig(data.config)
        setActiveProvider(data.config.active_provider)
        setOpenrouterEnabled(data.config.openrouter.enabled)
        setOpenrouterModel(data.config.openrouter.model)
        setAgentrouterEnabled(data.config.agentrouter.enabled)
        setAgentrouterModel(data.config.agentrouter.model)
        setAgentrouterBaseUrl(data.config.agentrouter.base_url)
        setAutoFallback(data.config.auto_fallback)
        
        if (data.agentrouter_cli_status) {
          setCliStatus(data.agentrouter_cli_status)
        }
      }
    } catch (error) {
      console.error('Failed to load AI provider config:', error)
      setMessage({ type: 'error', text: 'Failed to load configuration' })
    } finally {
      setLoading(false)
    }
  }

  const loadAvailableModels = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8743'}/api/ai-providers/models`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const data = await response.json()
      
      if (data.success && data.providers) {
        // API returns: { success: true, providers: { openrouter: { models: [...] }, agentrouter: { models: [...] } } }
        setAvailableModels({
          openrouter: Array.isArray(data.providers.openrouter?.models) 
            ? data.providers.openrouter.models 
            : [],
          agentrouter: Array.isArray(data.providers.agentrouter?.models) 
            ? data.providers.agentrouter.models 
            : []
        })
      } else {
        // Fallback to default models if API response structure is unexpected
        console.warn('Unexpected API response structure, using fallback models')
        setAvailableModels({
          openrouter: [
            { id: 'qwen/qwen3-max', name: 'Qwen 3 Max', description: 'Advanced reasoning (Recommended)', recommended: true },
            { id: 'deepseek-v3', name: 'DeepSeek V3', description: 'Fast and efficient' },
            { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', description: 'High quality reasoning' }
          ],
          agentrouter: [
            { id: 'qwen', name: 'Qwen', description: 'Advanced reasoning via CLI (Recommended)', recommended: true },
            { id: 'claude', name: 'Claude', description: 'Anthropic Claude via CLI' },
            { id: 'deepseek-v3.2', name: 'DeepSeek V3.2', description: 'Latest DeepSeek model' }
          ]
        })
      }
    } catch (error) {
      console.error('Failed to load available models:', error)
      // Fallback to default models on error
      setAvailableModels({
        openrouter: [
          { id: 'qwen/qwen3-max', name: 'Qwen 3 Max', description: 'Advanced reasoning (Recommended)', recommended: true },
          { id: 'deepseek-v3', name: 'DeepSeek V3', description: 'Fast and efficient' }
        ],
        agentrouter: [
          { id: 'qwen', name: 'Qwen', description: 'Advanced reasoning via CLI (Recommended)', recommended: true },
          { id: 'claude', name: 'Claude', description: 'Anthropic Claude via CLI' }
        ]
      })
    }
  }

  const checkCliStatus = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8743'}/api/ai-providers/cli-status`)
      const data = await response.json()
      
      if (data.success) {
        setCliStatus({
          installed: data.installed,
          running: data.running,
          version: data.version
        })
      }
    } catch (error) {
      console.error('Failed to check CLI status:', error)
    }
  }

  const testProvider = async (provider: 'openrouter' | 'agentrouter') => {
    try {
      setTesting({ provider })
      setMessage(null)
      
      const testConfig: any = {}
      if (provider === 'openrouter' && openrouterApiKey) {
        testConfig.api_key = openrouterApiKey
        testConfig.model = openrouterModel
      } else if (provider === 'agentrouter' && agentrouterApiKey) {
        testConfig.api_key = agentrouterApiKey
        testConfig.model = agentrouterModel
        testConfig.base_url = agentrouterBaseUrl
      }
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8743'}/api/ai-providers/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider,
          config: Object.keys(testConfig).length > 0 ? testConfig : null
        })
      })
      
      const data = await response.json()
      
      if (data.success) {
        setMessage({
          type: 'success',
          text: `✅ ${provider === 'openrouter' ? 'OpenRouter' : 'AgentRouter'} connection successful! Latency: ${data.details?.latency_ms}ms`
        })
      } else {
        setMessage({
          type: 'error',
          text: `❌ ${provider === 'openrouter' ? 'OpenRouter' : 'AgentRouter'} test failed: ${data.message}`
        })
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to test ${provider}: ${error}`
      })
    } finally {
      setTesting(null)
    }
  }

  const saveConfig = async () => {
    try {
      setSaving(true)
      setMessage(null)
      
      const payload = {
        active_provider: activeProvider,
        openrouter: {
          enabled: openrouterEnabled,
          api_key: openrouterApiKey || undefined,
          model: openrouterModel
        },
        agentrouter: {
          enabled: agentrouterEnabled,
          api_key: agentrouterApiKey || undefined,
          base_url: agentrouterBaseUrl,
          model: agentrouterModel
        },
        auto_fallback: autoFallback,
        fallback_order: [activeProvider === 'openrouter' ? 'openrouter' : 'agentrouter', 
                        activeProvider === 'openrouter' ? 'agentrouter' : 'openrouter']
      }
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8743'}/api/ai-providers/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      const data = await response.json()
      
      if (data.success) {
        setMessage({ type: 'success', text: '✅ AI provider configuration saved successfully!' })
        await loadConfig()
      } else {
        setMessage({ type: 'error', text: `❌ Failed to save: ${data.detail || 'Unknown error'}` })
      }
    } catch (error) {
      setMessage({ type: 'error', text: `Failed to save configuration: ${error}` })
    } finally {
      setSaving(false)
    }
  }

  const copyCommand = (command: string) => {
    navigator.clipboard.writeText(command)
    setMessage({ type: 'success', text: 'Command copied to clipboard!' })
    setTimeout(() => setMessage(null), 2000)
  }

  if (loading) {
    return (
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-slate-400">Loading AI provider settings...</span>
        </div>
      </div>
    )
  }

  const getStatusIcon = (status: string | null) => {
    switch (status) {
      case 'active': return '✅'
      case 'error': return '❌'
      case 'no_credits': return '⚠️'
      case 'not_running': return '⏸️'
      case 'not_installed': return '📦'
      default: return '⚪'
    }
  }

  const getStatusText = (status: string | null, provider: 'openrouter' | 'agentrouter') => {
    if (!status) return 'Not configured'
    
    switch (status) {
      case 'active': 
        return provider === 'openrouter' && config?.openrouter.credits_remaining 
          ? `Active (${config.openrouter.credits_remaining} credits remaining)`
          : 'Active'
      case 'error': return 'Connection error'
      case 'no_credits': return 'Insufficient credits'
      case 'not_running': return 'CLI not running'
      case 'not_installed': return 'CLI not installed'
      default: return 'Unknown status'
    }
  }

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">🤖 AI Recommendations Configuration</h2>
        <p className="text-slate-400 text-sm">
          Configure OpenRouter (cloud) or AgentRouter (local CLI) for AI-powered trading recommendations
        </p>
      </div>

      {message && (
        <div className={`mb-4 p-4 rounded-lg ${
          message.type === 'success' ? 'bg-green-500/20 border border-green-500/50 text-green-300' : 
          'bg-red-500/20 border border-red-500/50 text-red-300'
        }`}>
          {message.text}
        </div>
      )}

      {/* Active Provider Selection */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-slate-300 mb-3">Active Provider</label>
        <div className="flex gap-4">
          <button
            onClick={() => setActiveProvider('openrouter')}
            className={`flex-1 p-4 rounded-lg border-2 transition ${
              activeProvider === 'openrouter'
                ? 'border-blue-500 bg-blue-500/20 text-white'
                : 'border-slate-600 bg-slate-700/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <span className="text-2xl">☁️</span>
              <div className="text-left">
                <div className="font-semibold">OpenRouter</div>
                <div className="text-xs opacity-75">Cloud-based (Simple)</div>
              </div>
            </div>
          </button>
          
          <button
            onClick={() => setActiveProvider('agentrouter')}
            className={`flex-1 p-4 rounded-lg border-2 transition ${
              activeProvider === 'agentrouter'
                ? 'border-purple-500 bg-purple-500/20 text-white'
                : 'border-slate-600 bg-slate-700/50 text-slate-400 hover:border-slate-500'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <span className="text-2xl">💻</span>
              <div className="text-left">
                <div className="font-semibold">AgentRouter</div>
                <div className="text-xs opacity-75">Local CLI (Advanced)</div>
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* OpenRouter Configuration */}
      <div className="mb-6 p-4 rounded-lg bg-slate-700/30 border border-slate-600">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">☁️</span>
            <div>
              <h3 className="text-lg font-semibold text-white">OpenRouter</h3>
              <p className="text-xs text-slate-400">Cloud-based AI provider (Simple setup)</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm">
              {getStatusIcon(config?.openrouter.status)} {getStatusText(config?.openrouter.status || null, 'openrouter')}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {config?.openrouter.requests_count || 0} requests
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">
              API Key {config?.openrouter.api_key_set && <span className="text-green-400">(Set)</span>}
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={openrouterApiKey}
                onChange={(e) => setOpenrouterApiKey(e.target.value)}
                placeholder={config?.openrouter.api_key_preview || "sk-or-v1-..."}
                className="flex-1 px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={() => testProvider('openrouter')}
                disabled={testing?.provider === 'openrouter'}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testing?.provider === 'openrouter' ? 'Testing...' : 'Test'}
              </button>
            </div>
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
            >
              Get API key at openrouter.ai →
            </a>
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Model</label>
            <select
              value={openrouterModel}
              onChange={(e) => setOpenrouterModel(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              {availableModels.openrouter && availableModels.openrouter.length > 0 ? (
                availableModels.openrouter.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} {model.recommended ? '(Recommended)' : ''} - {model.description}
                  </option>
                ))
              ) : (
                <option value={openrouterModel}>{openrouterModel}</option>
              )}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="openrouter-enabled"
              checked={openrouterEnabled}
              onChange={(e) => setOpenrouterEnabled(e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-slate-900 border-slate-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="openrouter-enabled" className="text-sm text-slate-300">
              Enable OpenRouter
            </label>
          </div>
        </div>

        {config?.openrouter.last_error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-300">
              <strong>Last Error:</strong> {config.openrouter.last_error}
            </p>
          </div>
        )}
      </div>

      {/* AgentRouter Configuration */}
      <div className="mb-6 p-4 rounded-lg bg-slate-700/30 border border-slate-600">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">💻</span>
            <div>
              <h3 className="text-lg font-semibold text-white">AgentRouter</h3>
              <p className="text-xs text-slate-400">Local CLI-based provider (Requires setup)</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm">
              {getStatusIcon(config?.agentrouter.status)} {getStatusText(config?.agentrouter.status || null, 'agentrouter')}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {config?.agentrouter.requests_count || 0} requests
            </div>
          </div>
        </div>

        {/* CLI Installation Instructions */}
        {(!cliStatus?.running) && (
          <div className="mb-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <p className="text-sm text-yellow-300 mb-3 font-semibold">
              ⚠️ Qwen CLI Setup Required
            </p>
            <div className="space-y-2 text-sm text-slate-300">
              <div>
                <p className="text-xs text-slate-400 mb-1">Step 1: Install Qwen CLI</p>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-slate-900 rounded font-mono text-xs">
                    npm install -g qwen-cli
                  </code>
                  <button
                    onClick={() => copyCommand('npm install -g qwen-cli')}
                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                  >
                    Copy
                  </button>
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">Step 2: Start Qwen CLI</p>
                <div className="flex gap-2">
                  <code className="flex-1 px-3 py-2 bg-slate-900 rounded font-mono text-xs">
                    qwen start --port 3000
                  </code>
                  <button
                    onClick={() => copyCommand('qwen start --port 3000')}
                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs"
                  >
                    Copy
                  </button>
                </div>
              </div>
            </div>
            <button
              onClick={checkCliStatus}
              className="mt-3 text-xs text-blue-400 hover:text-blue-300"
            >
              🔄 Check CLI Status
            </button>
          </div>
        )}

        {cliStatus?.running && (
          <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
            <p className="text-sm text-green-300">
              ✅ Qwen CLI is running (version: {cliStatus.version || 'unknown'})
            </p>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">
              API Key {config?.agentrouter.api_key_set && <span className="text-green-400">(Set)</span>}
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={agentrouterApiKey}
                onChange={(e) => setAgentrouterApiKey(e.target.value)}
                placeholder={config?.agentrouter.api_key_preview || "sk-agent-..."}
                className="flex-1 px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={() => testProvider('agentrouter')}
                disabled={testing?.provider === 'agentrouter' || !cliStatus?.running}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testing?.provider === 'agentrouter' ? 'Testing...' : 'Test'}
              </button>
            </div>
            <a
              href="https://agentrouter.org/console/token"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-purple-400 hover:text-purple-300 mt-1 inline-block"
            >
              Get API key at agentrouter.org (for Qwen CLI) →
            </a>
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Base URL (CLI Endpoint)</label>
            <input
              type="text"
              value={agentrouterBaseUrl}
              onChange={(e) => setAgentrouterBaseUrl(e.target.value)}
              placeholder="http://localhost:3000"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Model</label>
            <select
              value={agentrouterModel}
              onChange={(e) => setAgentrouterModel(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
            >
              {availableModels.agentrouter && availableModels.agentrouter.length > 0 ? (
                availableModels.agentrouter.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} {model.recommended ? '(Recommended)' : ''} - {model.description}
                  </option>
                ))
              ) : (
                <option value={agentrouterModel}>{agentrouterModel}</option>
              )}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="agentrouter-enabled"
              checked={agentrouterEnabled}
              onChange={(e) => setAgentrouterEnabled(e.target.checked)}
              disabled={!cliStatus?.running}
              className="w-4 h-4 text-purple-600 bg-slate-900 border-slate-600 rounded focus:ring-purple-500 disabled:opacity-50"
            />
            <label htmlFor="agentrouter-enabled" className="text-sm text-slate-300">
              Enable AgentRouter (Qwen CLI) {!cliStatus?.running && <span className="text-yellow-500">(Qwen CLI must be running)</span>}
            </label>
          </div>
        </div>

        {config?.agentrouter.last_error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-300">
              <strong>Last Error:</strong> {config.agentrouter.last_error}
            </p>
          </div>
        )}
      </div>

      {/* Fallback Strategy */}
      <div className="mb-6 p-4 rounded-lg bg-slate-700/30 border border-slate-600">
        <h3 className="text-lg font-semibold text-white mb-4">🔄 Fallback Strategy</h3>
        
        <div className="flex items-center gap-2 mb-4">
          <input
            type="checkbox"
            id="auto-fallback"
            checked={autoFallback}
            onChange={(e) => setAutoFallback(e.target.checked)}
            className="w-4 h-4 text-blue-600 bg-slate-900 border-slate-600 rounded focus:ring-blue-500"
          />
          <label htmlFor="auto-fallback" className="text-sm text-slate-300">
            Enable automatic fallback
          </label>
        </div>

        {autoFallback && (
          <div className="text-sm text-slate-400 p-3 bg-slate-800/50 rounded-lg">
            <p className="mb-2">Priority Order:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>{activeProvider === 'openrouter' ? 'OpenRouter' : 'AgentRouter'} (Primary)</li>
              <li>{activeProvider === 'openrouter' ? 'AgentRouter' : 'OpenRouter'} (Fallback)</li>
            </ol>
            <p className="mt-2 text-xs text-slate-500">
              ℹ️ System will automatically switch to the next provider if the current one fails
            </p>
          </div>
        )}
      </div>

      {/* Save Button */}
      <div className="flex gap-4">
        <button
          onClick={saveConfig}
          disabled={saving}
          className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : '💾 Save Configuration'}
        </button>
        
        <button
          onClick={loadConfig}
          disabled={loading}
          className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition disabled:opacity-50"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Statistics */}
      {config && (
        <div className="mt-6 p-4 bg-slate-700/20 rounded-lg border border-slate-600">
          <h4 className="text-sm font-semibold text-slate-300 mb-3">📊 Usage Statistics</h4>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-slate-500 text-xs">Total Requests</p>
              <p className="text-white font-semibold">{config.statistics?.total_requests || 0}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">Fallback Triggered</p>
              <p className="text-white font-semibold">{config.statistics?.fallback_triggered || 0}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs">Last Request</p>
              <p className="text-white font-semibold text-xs">
                {config.statistics?.last_request_at 
                  ? new Date(config.statistics.last_request_at).toLocaleString() 
                  : 'Never'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

