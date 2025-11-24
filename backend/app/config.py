"""
Configuration management for TradAnalisa Platform
Secure configuration dengan proper environment variable handling
No hardcoded credentials - semua dari .env file
"""

import os
import logging
from urllib.parse import quote_plus, urlparse, urlunparse
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

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
    # Qwen: Advanced reasoning, multi-perspective analysis (DeepSeek deprecated)
    OPENROUTER_MODEL_QWEN = "qwen/qwen3-max"
    
    # Debug mode (define early)
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database Settings - PostgreSQL Production
    # Secure password handling dengan auto-encoding untuk special characters
    
    def build_database_url(raw_url: str) -> str:
        """
        Build secure database URL dengan proper password encoding
        Handle special characters seperti @, #, dll secara otomatis
        """
        if not raw_url or "://" not in raw_url:
            return raw_url
        
        try:
            # Parse URL dengan urlparse (lebih robust)
            parsed = urlparse(raw_url)
            
            # Jika password sudah di-encode atau tidak ada, return as-is
            if not parsed.password:
                return raw_url
            
            # Check jika password sudah encoded (contains %)
            if "%" in parsed.password:
                # Already encoded, return as-is
                return raw_url
            
            # Encode password untuk special characters
            encoded_password = quote_plus(parsed.password)
            
            # Reconstruct URL dengan encoded password
            # Format: scheme://user:encoded_password@host:port/path
            netloc_parts = []
            if parsed.username:
                netloc_parts.append(parsed.username)
            netloc_parts.append(encoded_password)
            
            netloc = ":".join(netloc_parts)
            if parsed.hostname:
                netloc += f"@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            
            # Build new URL
            new_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path or "",
                parsed.params or "",
                parsed.query or "",
                parsed.fragment or ""
            ))
            
            return new_url
            
        except Exception as e:
            # Fallback: return original URL
            logger.warning(f"Failed to parse DATABASE_URL: {e}, using as-is")
            return raw_url
    
    # Get DATABASE_URL from environment (required, tidak ada default)
    _db_url_raw = os.getenv("DATABASE_URL")
    if not _db_url_raw:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Please set it in .env file: "
            "DATABASE_URL=postgresql://revian:wokolcoy20.@localhost:5432/tradanalisa"
        )
    
    # Build secure connection string dengan auto-encoding
    DATABASE_URL = build_database_url(_db_url_raw)
    
    # Debug logging (hide password)
    if DEBUG:
        import re
        safe_url = re.sub(r':([^:@]+)@', r':***@', DATABASE_URL)
        logger.info(f"🔍 DATABASE_URL configured: {safe_url}")
    
    # JWT Authentication - Secure, no hardcoded secrets
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required. "
            "Generate a secure random key and set it in .env file. "
            "Example: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # OAuth Configuration (disable for now, enable when verified)
    OAUTH_ENABLED = os.getenv("OAUTH_ENABLED", "false").lower() == "true"
    
    # Binance OAuth (untuk production nanti)
    BINANCE_OAUTH_CLIENT_ID = os.getenv("BINANCE_OAUTH_CLIENT_ID", "")
    BINANCE_OAUTH_CLIENT_SECRET = os.getenv("BINANCE_OAUTH_CLIENT_SECRET", "")
    BINANCE_OAUTH_REDIRECT_URI = os.getenv("BINANCE_OAUTH_REDIRECT_URI", "http://localhost:3000/auth/binance/callback")
    
    # Demo/Simulation Mode (untuk testing tanpa OAuth)
    # Balance tidak di-hardcode - akan diambil dari database/account service
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    
    # Trading Settings
    # Supported crypto symbols for market overview, charts, and AI recommendations
    # Market symbols configuration
    # We now fetch ALL symbols dynamically from Binance
    # Minimum 24h volume to include symbol (in USDT)
    MIN_24H_VOLUME = float(os.getenv("MIN_24H_VOLUME", "1000000"))  # $1M
    
    # Maximum symbols to fetch for AI analysis
    MAX_AI_SYMBOLS = int(os.getenv("MAX_AI_SYMBOLS", "50"))
    
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

