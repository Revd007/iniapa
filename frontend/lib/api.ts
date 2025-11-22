/**
 * API Client for NOF1 Trading Bot Backend
 * Handles all communication with the Python FastAPI backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Available crypto symbols for market overview and trading
export const CRYPTO_SYMBOLS = [
  { symbol: 'BTC', name: 'Bitcoin', pair: 'BTCUSDT' },
  { symbol: 'ETH', name: 'Ethereum', pair: 'ETHUSDT' },
  { symbol: 'SOL', name: 'Solana', pair: 'SOLUSDT' },
  { symbol: 'BNB', name: 'Binance Coin', pair: 'BNBUSDT' },
  { symbol: 'XRP', name: 'Ripple', pair: 'XRPUSDT' },
  { symbol: 'BCH', name: 'Bitcoin Cash', pair: 'BCHUSDT' },
  { symbol: 'LTC', name: 'Litecoin', pair: 'LTCUSDT' },
  { symbol: 'ZEC', name: 'Zcash', pair: 'ZECUSDT' },
];

export interface MarketData {
  symbol: string;
  raw_symbol?: string;  // Original symbol format (e.g., "BTCUSDT") for search
  price: string;
  change: string;
  volume: string;
  high24h: string;
  low24h: string;
  raw_price: number;
  raw_change: number;
}

export interface AIRecommendation {
  symbol: string;
  name: string;
  signal: string;
  confidence: number;
  reason: string;
  riskLevel: string;
  color: string;
  timeframe: string;
  leverage?: string;
  entry_price?: string;
  target_price?: string;
  stop_loss?: string;
  is_fallback?: boolean;  // True if this is fallback data (not AI-generated)
  ai_model?: string;  // 'deepseek' or 'qwen'
  warning?: string | null;  // Warning message if AI unavailable
}

export interface ChartData {
  time: number;
  price: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20?: number;
  ma50?: number;
  rsi?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
}

export interface Trade {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  total_value: number;
  leverage: number;
  status: string;
  entry_price: number;
  exit_price?: number;
  profit_loss?: number;
  profit_loss_percent?: number;
  is_win?: boolean;
  created_at: string;
  closed_at?: string;
  trading_mode?: string;  // scalper, normal, aggressive, longhold
  ai_confidence?: number;  // If present, trade was executed by robot
  ai_reason?: string;
  ai_model?: string;
}

export interface PerformanceMetrics {
  total_profit: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  profit_percent: number;
  win_rate: number;
  risk_reward_ratio: string;
  trades_today: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
}

export interface PositionSummary {
  id: number;
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  break_even_price: number;
  mark_price: number;
  liq_price: number | null;
  margin_ratio: number;
  margin: number;
  pnl: number;
  roi_percent: number;
  est_funding_fee: number;
  leverage: number;
  stop_loss: number | null;
  take_profit: number | null;
  created_at: string;
  trading_mode?: string;  // scalper, normal, aggressive, longhold
  ai_confidence?: number;  // If present, position was opened by robot
  ai_reason?: string;
}

export interface AccountSummary {
  environment: 'demo' | 'live';
  base_balance: number;
  equity: number;
  available_balance: number;
  margin_used: number;
  realized_pnl: number;
  unrealized_pnl: number;
  trades_today: number;
}

// Market Data API
export const marketApi = {
  async getOverview(assetClass: 'crypto' | 'forex' = 'crypto'): Promise<MarketData[]> {
    const response = await fetch(`${API_BASE_URL}/api/market/overview?asset_class=${assetClass}`);
    const data = await response.json();
    return data.data || [];
  },

  async getTicker(symbol: string) {
    const response = await fetch(`${API_BASE_URL}/api/market/ticker/${symbol}`);
    const data = await response.json();
    return data.data;
  },

  async getOrderBook(symbol: string, limit: number = 10) {
    const response = await fetch(
      `${API_BASE_URL}/api/market/orderbook/${symbol}?limit=${limit}`
    );
    const data = await response.json();
    return data.data;
  },
};

// AI Recommendations API
export const aiApi = {
  async getRecommendations(
    mode: string, 
    assetClass: string = 'crypto', 
    limit: number = 6,
    aiModel: string = 'deepseek',  // 'deepseek' or 'qwen'
    pinnedSymbols?: string[]  // User's pinned symbols from market overview
  ): Promise<AIRecommendation[]> {
    // Build URL with pinned symbols if provided
    let url = `${API_BASE_URL}/api/ai/recommendations?mode=${mode}&asset_class=${assetClass}&limit=${limit}&ai_model=${aiModel}`;
    
    if (pinnedSymbols && pinnedSymbols.length > 0) {
      // Convert array to comma-separated string (e.g., "BTC/USDT,ETH/USDT")
      const pinnedStr = pinnedSymbols.join(',');
      url += `&pinned_symbols=${encodeURIComponent(pinnedStr)}`;
    }
    
    const response = await fetch(url);
    const data = await response.json();
    return data.recommendations || [];
  },

  async analyzeSymbol(symbol: string, mode: string = 'normal') {
    const response = await fetch(`${API_BASE_URL}/api/ai/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, mode }),
    });
    const data = await response.json();
    return data.analysis;
  },
};

// Chart Data API
export const chartApi = {
  async getKlines(symbol: string, interval: string = '1h', limit: number = 100, assetClass: 'crypto' | 'forex' = 'crypto'): Promise<ChartData[]> {
    const response = await fetch(
      `${API_BASE_URL}/api/charts/klines/${symbol}?interval=${interval}&limit=${limit}&asset_class=${assetClass}`
    );
    const data = await response.json();
    return data.data || [];
  },

  async getChartData(symbol: string, interval: string = '1h', limit: number = 100, assetClass: 'crypto' | 'forex' = 'crypto'): Promise<ChartData[]> {
    const response = await fetch(
      `${API_BASE_URL}/api/charts/chart/${symbol}?interval=${interval}&limit=${limit}&asset_class=${assetClass}`
    );
    const data = await response.json();
    return data.data || [];
  },

  async getRealtimePrice(symbol: string) {
    const response = await fetch(`${API_BASE_URL}/api/charts/realtime/${symbol}`);
    const data = await response.json();
    return data;
  },
};

// Trading API
export const tradingApi = {
  async executeTrade(tradeData: {
    symbol: string;
    side: string;
    quantity: number;
    order_type?: string;
    price?: number;
    leverage?: number;
    trading_mode?: string;
    ai_confidence?: number;
    ai_reason?: string;
    stop_loss?: number;
    take_profit?: number;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/trading/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tradeData),
    });
    const data = await response.json();
    return data;
  },

  async closeTrade(tradeId: number, exitPrice?: number) {
    const response = await fetch(`${API_BASE_URL}/api/trading/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade_id: tradeId, exit_price: exitPrice }),
    });
    const data = await response.json();
    return data;
  },

  async getOpenTrades(): Promise<Trade[]> {
    const response = await fetch(`${API_BASE_URL}/api/trading/open-trades`);
    const data = await response.json();
    return data.trades || [];
  },

  async getTradeHistory(limit: number = 50): Promise<Trade[]> {
    const response = await fetch(`${API_BASE_URL}/api/trading/trade-history?limit=${limit}`);
    const data = await response.json();
    return data.trades || [];
  },

  async getPositions(): Promise<{ positions: PositionSummary[]; auto_closed?: Array<{ id: number; symbol: string; reason: string }> }> {
    const response = await fetch(`${API_BASE_URL}/api/trading/positions`);
    const data = await response.json();
    return {
      positions: data.positions || [],
      auto_closed: data.auto_closed || []
    };
  },
};

// Performance API
export const performanceApi = {
  async getDashboard(assetClass: string = 'crypto'): Promise<{
    metrics: PerformanceMetrics;
    daily_profit: Array<{ day: string; profit: number }>;
    win_rate_distribution: Array<{ name: string; value: number }>;
  }> {
    const response = await fetch(
      `${API_BASE_URL}/api/performance/dashboard?asset_class=${assetClass}`
    );
    const data = await response.json();
    return data;
  },

  async getStats() {
    const response = await fetch(`${API_BASE_URL}/api/performance/stats`);
    const data = await response.json();
    return data.stats;
  },

  async getProfitChart(days: number = 30) {
    const response = await fetch(
      `${API_BASE_URL}/api/performance/profit-chart?days=${days}`
    );
    const data = await response.json();
    return data.chart_data || [];
  },
};

// Health Check
export const healthApi = {
  async check() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return await response.json();
  },
};

// Account
export const accountApi = {
  async getSummary(env?: 'demo' | 'live', assetClass: 'crypto' | 'forex' = 'crypto'): Promise<AccountSummary> {
    const params = new URLSearchParams();
    if (env) params.append('env', env);
    if (assetClass) params.append('asset_class', assetClass);
    const response = await fetch(`${API_BASE_URL}/api/account/summary?${params.toString()}`);
    const data = await response.json();
    return data;
  },
};

// Robot Trading API
export interface RobotConfig {
  enabled: boolean;
  min_confidence: number;
  max_positions: number;
  leverage: number;
  capital_per_trade: number;
  trading_mode: string;
  asset_class: string;
  strategies: string[];
  max_daily_loss: number;
  max_drawdown_percent: number;
  ai_models: string[];
  require_consensus: boolean;
  trade_cooldown_seconds: number;
  scan_interval_seconds: number;
  total_trades_executed: number;
  last_trade_at: string | null;
}

export interface RobotConfigUpdate {
  enabled?: boolean;
  min_confidence?: number;
  max_positions?: number;
  leverage?: number;
  capital_per_trade?: number;
  trading_mode?: string;
  asset_class?: string;
  strategies?: string[];
}

export const robotApi = {
  /**
   * Get robot trading configuration
   */
  async getConfig(): Promise<RobotConfig> {
    const response = await fetch(`${API_BASE_URL}/api/robot/config`);
    if (!response.ok) throw new Error('Failed to fetch robot config');
    return await response.json();
  },

  /**
   * Update robot trading configuration
   */
  async updateConfig(updates: RobotConfigUpdate): Promise<{ success: boolean; config: RobotConfig }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!response.ok) throw new Error('Failed to update robot config');
    return await response.json();
  },

  /**
   * Toggle robot ON/OFF
   */
  async toggle(): Promise<{ success: boolean; enabled: boolean }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/toggle`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to toggle robot');
    return await response.json();
  },

  /**
   * Get robot status and statistics
   */
  async getStatus(): Promise<{
    success: boolean;
    enabled: boolean;
    status: string;
    total_trades_executed: number;
    last_trade_at: string | null;
    current_positions: number;
    config: RobotConfig;
  }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/status`);
    if (!response.ok) throw new Error('Failed to fetch robot status');
    return await response.json();
  },

  /**
   * Start robot trading
   */
  async start(): Promise<{ success: boolean; message: string; enabled: boolean }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/start`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to start robot');
    return await response.json();
  },

  /**
   * Stop robot trading
   */
  async stop(): Promise<{ success: boolean; message: string; enabled: boolean }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/stop`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to stop robot');
    return await response.json();
  },

  /**
   * Trigger manual scan for trading opportunities
   */
  async triggerScan(): Promise<{ success: boolean; scanning: boolean; message?: string; error?: string }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/scan`, {
      method: 'POST',
    });
    const data = await response.json();
    
    // Check if response is ok AND success is true
    if (!response.ok || !data.success) {
      const errorMsg = data.error || data.message || 'Failed to trigger scan';
      throw new Error(errorMsg);
    }
    
    return data;
  },

  /**
   * Emergency stop - disable robot immediately
   */
  async stopAll(): Promise<{ success: boolean }> {
    const response = await fetch(`${API_BASE_URL}/api/robot/stop-all`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to stop robot');
    return await response.json();
  },
};

// User Settings API
export const userSettingsApi = {
  /**
   * Get user's pinned symbols for specific asset class
   */
  async getPinnedSymbols(assetClass: string): Promise<string[]> {
    const response = await fetch(`${API_BASE_URL}/api/user-settings/pinned-symbols?asset_class=${assetClass}`);
    if (!response.ok) {
      throw new Error('Failed to fetch pinned symbols');
    }
    const data = await response.json();
    return data.symbols || [];
  },

  /**
   * Update user's pinned symbols for specific asset class
   */
  async updatePinnedSymbols(assetClass: string, symbols: string[]): Promise<{ success: boolean }> {
    const response = await fetch(`${API_BASE_URL}/api/user-settings/pinned-symbols`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_class: assetClass, symbols }),
    });
    if (!response.ok) {
      throw new Error('Failed to update pinned symbols');
    }
    return await response.json();
  },
};

