"""
TradAnalisa Trading Platform - Production Backend
OAuth authentication, PostgreSQL database, dynamic symbol sync
Clean architecture with proper error handling and logging
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime
import logging
import asyncio

from app.routes import market, trading, performance, ai_recommendations, charts, account, auth, settings, robot, user_settings, ai_providers
from app.routes import account_comprehensive
from app.services.binance_service import BinanceService
from app.services.mt5_service import MT5Service
from app.services.market_sync_service import MarketSyncService
from app.services.robot_trading_service import robot_service
from app.database import init_db, get_db_context, check_db_connection
from app.config import settings as app_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Production lifespan handler:
    - PostgreSQL connection check
    - Database initialization
    - Market symbol synchronization
    - Background tasks
    """
    logger.info("🚀 Starting TradAnalisa Platform...")
    
    # Check PostgreSQL connection
    if not check_db_connection():
        logger.error("❌ PostgreSQL connection failed! Check DATABASE_URL in .env")
        logger.error("💡 Run 'python test_db_connection.py' to diagnose the issue")
        logger.error("💡 Or run 'python setup_database.py' to setup database")
        # Don't raise exception - let it continue with warning
        # raise Exception("Database connection failed")
    
    # Initialize database schema
    init_db()
    logger.info("✓ PostgreSQL database initialized")
    
    # Run migrations for new columns (if migration files exist)
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Run robot_configs.environment migration
        try:
            from migrate_add_environment import migrate_add_environment
            migrate_add_environment()
            logger.info("✓ Robot config environment migration completed")
        except Exception as e:
            logger.debug(f"Robot config migration (may already be applied): {e}")
        
        # Run api_credentials.environment migration
        try:
            from migrate_add_environment_to_api_credentials import migrate_add_environment_to_api_credentials
            migrate_add_environment_to_api_credentials()
            logger.info("✓ API credentials environment migration completed")
        except Exception as e:
            logger.debug(f"API credentials migration (may already be applied): {e}")
            
    except Exception as e:
        logger.warning(f"Migration warning: {e}")
    
    # Initialize Binance service
    binance_service = BinanceService()
    await binance_service.initialize()
    app.state.binance_service = binance_service
    logger.info("✓ Binance service initialized")
    
    # Initialize MT5 service (if enabled)
    mt5_service = MT5Service()
    await mt5_service.initialize()
    app.state.mt5_service = mt5_service
    logger.info("✓ MT5 service initialized")
    
    # Initialize market sync service
    market_sync = MarketSyncService(binance_service)
    app.state.market_sync = market_sync
    
    # Initialize robot trading service (DO NOT auto-start - safety first!)
    robot_service.set_binance_service(binance_service)
    logger.info("✓ Robot trading service initialized")
    logger.info("⚠️  SAFETY: Robot will NOT auto-start. Must be explicitly enabled via API.")
    
    # Sync crypto symbols on startup (non-blocking)
    async def initial_sync():
        with get_db_context() as db:
            try:
                count = await market_sync.sync_crypto_symbols(db)
                logger.info(f"✓ Synced {count} crypto symbols from Binance")
            except Exception as e:
                logger.error(f"Failed to sync symbols: {e}")
    
    # Run sync in background
    asyncio.create_task(initial_sync())
    
    # Start background task for periodic symbol sync (every 6 hours)
    async def periodic_symbol_sync():
        while True:
            await asyncio.sleep(6 * 60 * 60)  # 6 hours
            with get_db_context() as db:
                try:
                    count = await market_sync.sync_crypto_symbols(db)
                    logger.info(f"🔄 Periodic sync: {count} symbols updated")
                except Exception as e:
                    logger.error(f"Periodic sync failed: {e}")
    
    sync_task = asyncio.create_task(periodic_symbol_sync())
    
    logger.info("✅ TradAnalisa Platform ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down TradAnalisa Platform...")
    sync_task.cancel()
    await binance_service.close()
    await mt5_service.close()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="TradAnalisa API",
    description="Production trading platform with OAuth, PostgreSQL, and AI",
    version="2.0.0",
    lifespan=lifespan
)

# Session middleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=app_settings.JWT_SECRET_KEY,
    session_cookie="tradanalisa_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=False  # Set to True in production with HTTPS
)

# CORS middleware - allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5237",
        "http://127.0.0.1:5237",
        "http://localhost:3000",  # Keep old port for compatibility
        "http://127.0.0.1:3000",  # Keep old port for compatibility
        "http://100.85.124.82:5237",  # Network IP
        "http://100.85.124.82:3000",  # Network IP old port
        "https://tradanalisa.dutatravel.net",  # Production domain
        "https://www.tradanalisa.dutatravel.net",  # Production domain with www
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "online",
        "service": "NOF1 Trading Bot API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "operational",
            "database": "operational",
            "binance": "operational"
        }
    }


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(market.router, prefix="/api/market", tags=["Market Data"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(performance.router, prefix="/api/performance", tags=["Performance"])
app.include_router(ai_recommendations.router, prefix="/api/ai", tags=["AI Recommendations"])
app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])
app.include_router(account_comprehensive.router, prefix="/api/account", tags=["Account"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(robot.router, prefix="/api/robot", tags=["Robot Trading"])
app.include_router(user_settings.router, prefix="/api/user-settings", tags=["User Settings"])
app.include_router(ai_providers.router, prefix="/api/ai-providers", tags=["AI Providers"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8743,
        reload=True,
        log_level="info",
        # Optimize for faster startup
        access_log=False,  # Disable access logs for faster startup
        loop="asyncio",  # Use asyncio event loop (faster than uvloop on Windows)
    )

