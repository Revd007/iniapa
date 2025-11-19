"""
Configuration management for NOF1 Trading Bot
Loads environment variables and provides configuration settings
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class Settings:
    """Application settings"""
    
    # API Settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    
    # Binance API Settings (Live / Demo Testnet)
    # We route keys based on BINANCE_TESTNET flag so it's explicit which env is used.
    BINANCE_TESTNET = (
        os.getenv("BINANCE_TESTNET")
        or os.getenv("BINANCE_DEMO_TESTNET")
        or os.getenv("BINANCE_LIVE_TESTNET")
        or "true"
    )
    BINANCE_TESTNET = str(BINANCE_TESTNET).lower() == "true"

    # Live keys (real account - use with care)
    BINANCE_LIVE_API_KEY = os.getenv("BINANCE_LIVE_API_KEY", "")
    BINANCE_LIVE_API_SECRET = os.getenv("BINANCE_LIVE_API_SECRET", "")

    # Demo / Testnet keys (safe for testing)
    BINANCE_DEMO_API_KEY = os.getenv("BINANCE_DEMO_API_KEY", "")
    BINANCE_DEMO_API_SECRET = os.getenv("BINANCE_DEMO_SECRET_KEY", "")

    # Selected keys depending on environment
    BINANCE_API_KEY = BINANCE_DEMO_API_KEY if BINANCE_TESTNET else BINANCE_LIVE_API_KEY
    BINANCE_API_SECRET = BINANCE_DEMO_API_SECRET if BINANCE_TESTNET else BINANCE_LIVE_API_SECRET

    # Paper trading toggle (if true, we do NOT send real orders to Binance even if keys are valid)
    BINANCE_PAPER_TRADING = os.getenv("BINANCE_PAPER_TRADING", "false").lower() == "true"
    
    # Binance Testnet URLs
    BINANCE_TESTNET_BASE_URL = "https://testnet.binance.vision/api"
    BINANCE_TESTNET_WS_URL = "wss://testnet.binance.vision/ws"
    BINANCE_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
    
    # Production URLs (for future use)
    BINANCE_BASE_URL = "https://api.binance.com/api"
    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
    
    # OpenRouter AI Settings
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # AI Models for trading recommendations
    # DeepSeek: Fast, cost-effective, good for technical analysis
    OPENROUTER_MODEL_DEEPSEEK = "deepseek/deepseek-chat-v3"
    # Qwen: Advanced reasoning, multi-perspective analysis
    OPENROUTER_MODEL_QWEN = "qwen/qwen-2.5-72b-instruct"
    
    # Database Settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nof1_trading.db")
    
    # Trading Settings
    # Supported crypto symbols for market overview, charts, and AI recommendations
    SUPPORTED_SYMBOLS = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "BCHUSDT", "LTCUSDT", "ZECUSDT"  # Added: Bitcoin Cash, Litecoin, Zcash
    ]
    DEFAULT_TRADING_MODE = "normal"

    # MT5 (MetaTrader 5) Settings for FOREX
    MT5_ENABLED = os.getenv("MT5_ENABLED", "false").lower() == "true"
    MT5_DEMO_LOGIN = os.getenv("MT5_DEMO_LOGIN", "")
    MT5_DEMO_PASSWORD = os.getenv("MT5_DEMO_PASSWORD", "")
    MT5_DEMO_SERVER = os.getenv("MT5_DEMO_SERVER", "")

    MT5_LIVE_LOGIN = os.getenv("MT5_LIVE_LOGIN", "")
    MT5_LIVE_PASSWORD = os.getenv("MT5_LIVE_PASSWORD", "")
    MT5_LIVE_SERVER = os.getenv("MT5_LIVE_SERVER", "")

    # MT5 environment selection: demo/live
    MT5_ENV = os.getenv("MT5_ENV", "demo").lower()  # demo | live
    
    # Cache Settings
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", 60))  # seconds
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def binance_api_url(self):
        """Get appropriate Binance API URL based on environment"""
        return self.BINANCE_TESTNET_BASE_URL if self.BINANCE_TESTNET else self.BINANCE_BASE_URL
    
    @property
    def binance_ws_url(self):
        """Get appropriate Binance WebSocket URL based on environment"""
        return self.BINANCE_TESTNET_WS_URL if self.BINANCE_TESTNET else self.BINANCE_WS_URL


settings = Settings()

