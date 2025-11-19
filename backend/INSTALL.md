# Installation Guide - NOF1 Trading Bot Backend

Complete installation guide for the Python backend.

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, Linux, or macOS
- **RAM**: Minimum 2GB
- **Internet**: Required for API access

## Installation Methods

### Method 1: Automated Setup (Recommended)

#### Windows
1. Open Command Prompt or PowerShell
2. Navigate to backend folder:
   ```cmd
   cd path\to\nof1beta\backend
   ```
3. Run setup script:
   ```cmd
   setup.bat
   ```

#### Linux/Mac
1. Open Terminal
2. Navigate to backend folder:
   ```bash
   cd path/to/nof1beta/backend
   ```
3. Make scripts executable:
   ```bash
   chmod +x setup.sh start.sh
   ```
4. Run setup script:
   ```bash
   ./setup.sh
   ```

### Method 2: Manual Setup

#### Step 1: Create Virtual Environment

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 3: Configure Environment

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` file with your credentials (see below)

## API Keys Configuration

### 1. Binance Testnet Keys (Required)

The backend uses Binance Testnet for safe demo trading.

**Get Your Keys:**

1. Visit: https://testnet.binance.vision/
2. Click on "Generate HMAC_SHA256 Key"
3. Save both:
   - **API Key** (starts with a long string)
   - **Secret Key** (keep this secret!)

**Add to .env:**
```env
BINANCE_API_KEY=your_api_key_from_testnet
BINANCE_API_SECRET=your_secret_key_from_testnet
BINANCE_TESTNET=true
```

**Test Fund Your Testnet Account:**
- The testnet provides test USDT
- No real money required
- Perfect for learning and testing

### 2. OpenRouter API Key (Required for AI)

OpenRouter provides access to DeepSeek AI for trading recommendations.

**Get Your Key:**

1. Visit: https://openrouter.ai/
2. Click "Sign Up" (can use Google/GitHub)
3. Go to "Keys" section
4. Click "Create Key"
5. Add credits to your account:
   - Click "Credits"
   - Add $5-10 to start (enough for ~5,000 AI recommendations)
6. Copy your API key

**Add to .env:**
```env
OPENROUTER_API_KEY=sk-or-v1-your_key_here
```

**Pricing:**
- DeepSeek V3: ~$0.27 per 1M input tokens
- ~$1.10 per 1M output tokens
- Very affordable compared to GPT-4
- $10 credit = thousands of recommendations

## Starting the Backend

### Windows
```cmd
start.bat
```

### Linux/Mac
```bash
./start.sh
```

The backend will start on: http://localhost:8000

## Verify Installation

### 1. Check API Health

Open browser and visit:
```
http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "timestamp": "2024-...",
  "services": {
    "api": "operational",
    "database": "operational",
    "binance": "operational"
  }
}
```

### 2. Test Market Data

```
http://localhost:8000/api/market/overview
```

Should return real-time crypto prices for BTC, ETH, SOL, BNB, XRP.

### 3. Test AI Recommendations

Visit: http://localhost:8000/docs

1. Find `/api/ai/recommendations` endpoint
2. Click "Try it out"
3. Select mode: `normal`
4. Click "Execute"

You should see 3 AI-powered trading recommendations!

## Troubleshooting

### Python Not Found

**Windows:**
1. Download Python from python.org
2. During installation, check "Add Python to PATH"
3. Restart Command Prompt

**Linux:**
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

**Mac:**
```bash
brew install python3
```

### Permission Denied (Linux/Mac)

Make scripts executable:
```bash
chmod +x setup.sh start.sh
```

### Module Not Found Errors

1. Ensure virtual environment is activated:
   ```bash
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Binance API Errors

**Error: "Invalid API Key"**
- Double-check API key in `.env`
- Ensure no extra spaces
- Verify key is from testnet.binance.vision (not regular Binance)

**Error: "Signature verification failed"**
- Check API Secret is correct
- Ensure `BINANCE_TESTNET=true`
- Try generating new keys

**Error: "Connection refused"**
- Check internet connection
- Verify testnet is accessible: https://testnet.binance.vision/

### OpenRouter API Errors

**Error: "Invalid API Key"**
- Verify key starts with `sk-or-v1-`
- Check for typos in `.env` file
- Try creating new key at openrouter.ai

**Error: "Insufficient credits"**
- Add credits at https://openrouter.ai/credits
- $5 minimum recommended

**Error: "Rate limit exceeded"**
- Wait a few seconds between requests
- Consider upgrading credits tier

### Port Already in Use

If port 8000 is busy:

1. Change port in `.env`:
   ```env
   API_PORT=8001
   ```

2. Or find and stop the process:

**Windows:**
```cmd
netstat -ano | findstr :8000
taskkill /PID <process_id> /F
```

**Linux/Mac:**
```bash
lsof -i :8000
kill -9 <process_id>
```

### Database Errors

If you see database errors:

1. Delete old database:
   ```bash
   rm nof1_trading.db
   ```

2. Restart backend (will create new database)

## Production Deployment

### Switch to Production Binance

⚠️ **Only after thorough testing on testnet!**

1. Get production API keys from binance.com
2. Update `.env`:
   ```env
   BINANCE_TESTNET=false
   BINANCE_API_KEY=your_production_key
   BINANCE_API_SECRET=your_production_secret
   ```

### Use Production Database

Replace SQLite with PostgreSQL:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/nof1trading
```

Install psycopg2:
```bash
pip install psycopg2-binary
```

### Deploy to Server

**Using systemd (Linux):**

Create `/etc/systemd/system/nof1-backend.service`:
```ini
[Unit]
Description=NOF1 Trading Bot Backend
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/backend/venv/bin"
ExecStart=/path/to/backend/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nof1-backend
sudo systemctl start nof1-backend
```

**Using Docker:**

See `Dockerfile` (to be created) for containerized deployment.

## Security Best Practices

1. **Never Commit .env File**
   - Added to `.gitignore`
   - Contains sensitive API keys

2. **Use Environment Variables**
   - Don't hardcode API keys
   - Use `.env` file only

3. **Start with Testnet**
   - Test thoroughly before production
   - No real money at risk

4. **Implement Authentication**
   - Add API key authentication
   - Use JWT tokens for frontend

5. **Enable HTTPS**
   - Use reverse proxy (nginx)
   - Get SSL certificate (Let's Encrypt)

6. **Monitor Logs**
   - Check for suspicious activity
   - Set up alerts for errors

## Updates and Maintenance

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Backup Database

```bash
cp nof1_trading.db nof1_trading.db.backup
```

### View Logs

Logs are printed to console. For persistent logs:

```bash
python main.py > backend.log 2>&1
```

## Support Resources

- **Quick Start**: See `QUICKSTART.md`
- **Full Documentation**: See `README.md`
- **API Documentation**: http://localhost:8000/docs
- **Binance API Docs**: https://developers.binance.com/
- **OpenRouter Docs**: https://openrouter.ai/docs

## Next Steps

After successful installation:

1. ✅ Backend running on http://localhost:8000
2. 📊 Explore API at http://localhost:8000/docs
3. 🤖 Test AI recommendations
4. 💹 Practice with demo trades
5. 📈 Monitor your performance
6. 🎯 Connect frontend at http://localhost:3000

Happy Trading! 🚀

