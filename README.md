# Tradanalisa Trading Platform

Platform trading crypto otomatis dengan AI recommendations dan robot trading yang cerdas. Built with Next.js 16, FastAPI, PostgreSQL, dan integrasi Binance API.

## 🏗️ Arsitektur Sistem

### Overview
Platform ini menggunakan **microservices architecture** dengan:
- **Frontend**: Next.js 16 (React) dengan TypeScript
- **Backend**: FastAPI (Python) dengan PostgreSQL
- **External APIs**: Binance API (Crypto), MT5 (Forex - optional), OpenRouter AI

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Next.js App   │────────▶│   FastAPI Backend │────────▶│   PostgreSQL    │
│  (Frontend)     │  REST   │   (Backend)      │  ORM    │   (Database)    │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                     │
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
        ┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
        │  Binance API  │   │  OpenRouter   │   │  MT5 Service  │
        │  (Trading)    │   │  (AI Models)  │   │  (Forex)      │
        └───────────────┘   └───────────────┘   └───────────────┘
```

## 📁 Struktur Project

```
Tradanalisabeta/
├── app/                          # Next.js App Directory
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Main dashboard page
│   ├── globals.css              # Global styles
│   └── favicon.ico              # Favicon
│
├── components/                   # React Components
│   ├── ai-recommendations-dual.tsx    # AI recommendations (DeepSeek + Qwen)
│   ├── asset-selector.tsx              # Asset class selector (Crypto/Forex/Stocks)
│   ├── candlestick-chart-with-indicators.tsx  # Chart dengan indicators (MA, RSI, MACD, Bollinger)
│   ├── chart-panel.tsx                 # Chart container panel
│   ├── header.tsx                     # Header dengan account balance & settings
│   ├── market-overview.tsx            # Market overview dengan search & pin
│   ├── open-positions.tsx             # Open positions banner
│   ├── performance-dashboard.tsx      # Performance metrics dashboard
│   ├── robot-trading.tsx              # Robot trading configuration & control
│   ├── settings-modal.tsx             # Settings modal untuk API keys
│   ├── trade-execution.tsx            # Manual trade execution
│   ├── trade-history.tsx              # Trade history table
│   └── trading-mode-selector.tsx      # Trading mode selector (Scalper/Normal/Aggressive/Longhold)
│
├── lib/                          # Utility Libraries
│   ├── api.ts                    # API client untuk semua backend endpoints
│   └── utils.ts                  # Utility functions
│
├── backend/                      # FastAPI Backend
│   ├── main.py                   # FastAPI app entry point
│   ├── requirements.txt          # Python dependencies
│   │
│   └── app/                      # Application package
│       ├── __init__.py
│       ├── config.py             # Configuration & settings
│       ├── database.py           # Database connection & initialization
│       ├── models.py             # SQLAlchemy models
│       │
│       ├── routes/               # API Routes
│       │   ├── account.py        # Account balance & summary
│       │   ├── ai_recommendations.py  # AI recommendations endpoints
│       │   ├── auth.py           # Authentication endpoints
│       │   ├── charts.py         # Chart data & indicators
│       │   ├── market.py         # Market overview & symbol sync
│       │   ├── performance.py    # Performance analytics
│       │   ├── robot.py          # Robot trading control
│       │   ├── settings.py       # API keys management
│       │   ├── trading.py        # Trade execution & positions
│       │   └── user_settings.py  # User settings (pinned symbols)
│       │
│       └── services/             # Business Logic Services
│           ├── ai_service.py              # AI recommendation service (OpenRouter)
│           ├── auth_service.py            # Authentication service
│           ├── binance_service.py         # Binance API integration
│           ├── demo_account_service.py    # Demo account simulation
│           ├── market_sync_service.py     # Market symbol synchronization
│           ├── mt5_service.py             # MT5 integration (Forex)
│           ├── robot_config_service.py    # Robot configuration management
│           └── robot_trading_service.py   # Robot trading automation
│
├── public/                       # Static assets
├── package.json                  # Node.js dependencies
├── tailwind.config.js            # Tailwind CSS configuration
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # This file
```

## 🎯 Fitur Utama

### 1. **AI-Powered Trading Recommendations**
- **Multi-Model AI**: DeepSeek & Qwen models via OpenRouter
- **Smart Analysis**: Technical indicators (RSI, MACD, MA, Bollinger Bands)
- **Clear Signals**: Entry, Target Price, Stop Loss dengan confidence %
- **Mode-Aware**: Recommendations mengikuti trading mode (Scalper/Normal/Aggressive/Longhold)

### 2. **Robot Trading Automation**
- **Automated Execution**: Scan market setiap X detik
- **AI-Driven**: Mengikuti AI recommendations dengan confidence threshold
- **Risk Management**: 
  - Max positions limit
  - Max daily loss protection
  - Trade cooldown
  - Stop Loss & Take Profit otomatis
- **Mode-Adaptive**: Mengikuti trading mode yang dipilih
- **Duplicate Prevention**: Tidak entry symbol yang sama berulang

### 3. **Advanced Charting**
- **Candlestick Chart**: High-quality rendering dengan Canvas API
- **Technical Indicators**:
  - Moving Averages (MA20, MA50)
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands
- **Interactive**: Zoom, pan, crosshair, tooltip
- **Responsive**: Mobile-first design
- **TradingView-like**: Professional appearance

### 4. **Market Overview**
- **Real-time Data**: 24h ticker data dari Binance
- **Symbol Search**: Search & filter symbols
- **Pin/Unpin**: Pinned symbols tersimpan di database
- **Auto-Sync**: Symbol sync otomatis dari Binance

### 5. **Trade Management**
- **Demo & Live Mode**: Paper trading & real trading
- **Position Tracking**: Open positions dengan unrealized P&L
- **Trade History**: Complete trade history dengan statistics
- **Auto-Close**: Auto-close pada TP/SL hit
- **Performance Dashboard**: Win rate, total P&L, ROI

### 6. **User Settings**
- **API Keys Management**: Secure storage dengan encryption
- **Pinned Symbols**: Per-user pinned symbols per asset class
- **Robot Configuration**: Customizable robot settings
- **Balance Display**: Demo & real account balance

## 🔧 Tech Stack

### Frontend
- **Next.js 16**: React framework dengan App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **Canvas API**: High-performance chart rendering

### Backend
- **FastAPI**: Modern Python web framework
- **PostgreSQL**: Relational database
- **SQLAlchemy**: ORM untuk database operations
- **Pydantic**: Data validation
- **Asyncio**: Async/await untuk concurrent operations

### External Services
- **Binance API**: Crypto market data & trading
- **OpenRouter API**: AI model access (DeepSeek, Qwen)
- **MT5 API**: Forex trading (optional)

## 🗄️ Database Schema

### Core Tables
- **users**: User accounts
- **user_settings**: User preferences (pinned symbols)
- **user_api_keys**: Encrypted API keys
- **market_symbols**: Market symbols dengan metadata
- **trades**: Trade history & open positions
- **robot_configs**: Robot trading configuration
- **performance_stats**: Performance analytics

### Key Relationships
```
User
  ├── UserSettings (1:1)
  ├── UserAPIKey (1:1)
  ├── Trade (1:N)
  └── RobotConfig (1:1)
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- PostgreSQL 14+

### Installation

1. **Clone repository**
```bash
git clone <repository-url>
cd Tradanalisabeta
```

2. **Setup Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Setup Frontend**
```bash
npm install
```

4. **Configure Environment**
```bash
# Backend: backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/Tradanalisabeta
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
OPENROUTER_API_KEY=your_key

# Frontend: .env.local (optional)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

5. **Initialize Database**
```bash
cd backend
python main.py  # Auto-initializes database on first run
```

6. **Start Development Servers**
```bash
# Terminal 1: Backend
cd backend
python main.py

# Terminal 2: Frontend
npm run dev
```

7. **Access Application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📊 API Endpoints

### Market
- `GET /api/market/overview` - Market overview data
- `GET /api/market/symbols` - Available symbols
- `GET /api/market/search` - Search symbols

### Trading
- `POST /api/trading/execute` - Execute trade
- `POST /api/trading/close` - Close position
- `GET /api/trading/positions` - Open positions
- `GET /api/trading/trade-history` - Trade history

### AI Recommendations
- `GET /api/ai/recommendations` - Get AI recommendations
- Query params: `mode`, `asset_class`, `limit`, `ai_model`, `pinned_symbols`

### Robot Trading
- `POST /api/robot/start` - Start robot
- `POST /api/robot/stop` - Stop robot
- `POST /api/robot/scan` - Manual scan
- `GET /api/robot/status` - Robot status
- `PUT /api/robot/config` - Update config

### Charts
- `GET /api/charts/klines` - Candlestick data
- `GET /api/charts/indicators` - Technical indicators

### Account & Settings
- `GET /api/account/summary` - Account summary
- `POST /api/settings/api-keys` - Save API keys
- `GET /api/user-settings/pinned-symbols/{asset_class}` - Get pinned symbols
- `POST /api/user-settings/pinned-symbols/{asset_class}` - Update pinned symbols

## 🔐 Security

- **API Key Encryption**: Fernet encryption untuk Binance API keys
- **CORS**: Configured untuk development & production
- **Rate Limiting**: Token bucket algorithm untuk Binance API
- **Input Validation**: Pydantic models untuk request validation

## 📈 Trading Modes

1. **Scalper**: Fast trades, 1-5min timeframe, 5-10x leverage
2. **Normal**: Balanced, 1H-4H timeframe, 1-5x leverage
3. **Aggressive**: Quick profits, 15min-1H timeframe, 5-15x leverage
4. **Longhold**: Long-term, Daily-Monthly timeframe, 1-2x leverage

## 🤖 Robot Trading Flow

```
1. Robot Started
   ↓
2. Scan Market (every X seconds)
   ↓
3. Get AI Recommendations
   ↓
4. Filter by Confidence Threshold
   ↓
5. Filter out HOLD signals
   ↓
6. Filter out duplicate positions
   ↓
7. Select Best Recommendation (highest confidence)
   ↓
8. Safety Checks (max positions, max loss, cooldown)
   ↓
9. Execute Trade (with SL/TP from AI)
   ↓
10. Wait for Scan Interval
   ↓
   Repeat from step 2
```

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
# Verify DATABASE_URL in backend/.env
# Run: python backend/test_db_connection.py
```

### Binance API Errors
```bash
# Check API keys in Settings modal
# Verify API key permissions (Read & Trade)
# Check rate limits in terminal logs
```

### Robot Not Trading
- Check robot is enabled (START button)
- Check confidence threshold (lower if needed)
- Check max positions limit
- Check logs for AI recommendations
- Verify pinned symbols exist

## 📝 Development Notes

- **Code Style**: Follow PEP 8 (Python) & ESLint (TypeScript)
- **Database Migrations**: Use Alembic for schema changes
- **Error Handling**: Comprehensive error logging
- **Testing**: Manual testing via frontend & API docs

## 📄 License

MIT License

## 👥 Contributors

- Development Team

## 🔗 Links

- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/)
- [OpenRouter Documentation](https://openrouter.ai/docs)

---

**Last Updated**: 2025-11-24
