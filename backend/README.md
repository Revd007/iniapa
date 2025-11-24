# NOF1 Trading Bot - Backend

AI-powered cryptocurrency trading bot backend with Binance integration and Qwen AI recommendations.

## Features

- 📊 **Real-time Market Data**: Live crypto prices from Binance (BTC, ETH, SOL, BNB, XRP)
- 🤖 **AI Trading Recommendations**: Powered by Qwen AI via OpenRouter
- 📈 **Performance Tracking**: Win rate, profit/loss, risk/reward metrics
- 💹 **Chart Data**: Candlestick charts with technical indicators (MA20, MA50, RSI)
- ⚡ **Quick Execute**: Fast trade execution with position tracking
- 🎯 **4 Trading Modes**: Scalper, Normal, Aggressive, Long Hold

## Trading Modes

### Scalper Mode
- **Timeframe**: 1-5 minutes
- **Risk Level**: Very High
- **Leverage**: 5-10x
- **Strategy**: Quick in-and-out trades, high frequency

### Normal Mode
- **Timeframe**: 30min - 4H
- **Risk Level**: Medium to High
- **Leverage**: 1-5x
- **Strategy**: Balanced approach, trend following

### Aggressive Mode
- **Timeframe**: 15min - 1H
- **Risk Level**: Very High
- **Leverage**: 5-15x
- **Strategy**: High-risk high-reward, breakout trading

### Long Hold Mode
- **Timeframe**: Daily to Monthly
- **Risk Level**: Low to Medium
- **Leverage**: 1-2x
- **Strategy**: Long-term investment, fundamentals

## Setup

### 1. Install Python Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the backend directory:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Binance Testnet API Keys
# Get from: https://testnet.binance.vision/
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true

# OpenRouter API Key
# Get from: https://openrouter.ai/
OPENROUTER_API_KEY=your_openrouter_key_here
```

### 3. Get API Keys

#### Binance Testnet (for demo trading)
1. Visit https://testnet.binance.vision/
2. Sign up for a testnet account
3. Generate API keys
4. Add to `.env` file

#### OpenRouter (for AI recommendations)
1. Visit https://openrouter.ai/
2. Create an account
3. Add credits to your account
4. Generate API key
5. Add to `.env` file

### 4. Run the Backend

```bash
cd backend
python main.py
```

The API will start on `http://localhost:8000`

Visit `http://localhost:8000/docs` for interactive API documentation.

## API Endpoints

### Market Data
- `GET /api/market/overview` - Get market overview for BTC, ETH, SOL, BNB, XRP
- `GET /api/market/ticker/{symbol}` - Get ticker data for symbol
- `GET /api/market/orderbook/{symbol}` - Get order book depth

### AI Recommendations
- `GET /api/ai/recommendations?mode={mode}` - Get AI trading recommendations
  - Modes: `scalper`, `normal`, `aggressive`, `longhold`
- `POST /api/ai/analyze` - Analyze specific trade opportunity

### Trading
- `POST /api/trading/execute` - Execute a trade
- `POST /api/trading/close` - Close an open trade
- `GET /api/trading/open-trades` - Get all open trades
- `GET /api/trading/trade-history` - Get trade history

### Performance
- `GET /api/performance/dashboard` - Get performance dashboard metrics
- `GET /api/performance/stats` - Get detailed statistics
- `GET /api/performance/profit-chart?days={days}` - Get profit chart data

### Charts
- `GET /api/charts/klines/{symbol}` - Get candlestick data
- `GET /api/charts/chart/{symbol}` - Get formatted chart data with indicators
- `GET /api/charts/realtime/{symbol}` - Get real-time price

## Database

The backend uses SQLite for data persistence:
- **Trades**: All executed trades with P/L tracking
- **Performance Metrics**: Daily performance statistics

Database file: `nof1_trading.db`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── database.py         # Database models and setup
│   ├── routes/             # API endpoints
│   │   ├── market.py       # Market data endpoints
│   │   ├── ai_recommendations.py
│   │   ├── trading.py      # Trading execution
│   │   ├── performance.py  # Performance metrics
│   │   └── charts.py       # Chart data
│   └── services/           # Business logic
│       ├── binance_service.py  # Binance API integration
│       └── ai_service.py       # AI recommendations
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Development

### Running with Auto-reload

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing API

Visit the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Logs

The backend provides detailed logging for debugging:
- API requests and responses
- Binance API calls
- AI recommendation generation
- Trade execution
- Errors and exceptions

## Production Deployment

For production use:

1. **Switch to Production Binance API**:
   ```env
   BINANCE_TESTNET=false
   BINANCE_API_KEY=your_production_key
   BINANCE_API_SECRET=your_production_secret
   ```

2. **Use Production Database**:
   ```env
   DATABASE_URL=postgresql://user:pass@host:5432/db
   ```

3. **Secure the API**:
   - Add authentication middleware
   - Use HTTPS
   - Implement rate limiting
   - Add API key authentication

4. **Run with Production Server**:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
   ```

## Security Notes

⚠️ **Important**:
- Never commit `.env` file to version control
- Keep your API keys secure
- Use testnet for development/testing
- Start with small amounts when using real funds
- Implement proper authentication in production

## Support

For issues or questions:
1. Check the API documentation at `/docs`
2. Review logs for error messages
3. Verify API keys are correct
4. Ensure Binance testnet is accessible

## License

MIT License - See LICENSE file for details
