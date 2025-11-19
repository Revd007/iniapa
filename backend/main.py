"""
NOF1 Trading Bot - FastAPI Backend
Main application entry point with API routes
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime
import logging

from app.routes import market, trading, performance, ai_recommendations, charts, account
from app.services.binance_service import BinanceService
from app.services.mt5_service import MT5Service
from app.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup - Optimized for fast startup
    logger.info("Starting NOF1 Trading Bot Backend...")
    
    # Initialize database (fast - SQLite is quick)
    init_db()
    logger.info("✓ Database initialized")
    
    # Initialize Binance service (crypto) - lightweight, just creates session
    binance_service = BinanceService()
    await binance_service.initialize()
    app.state.binance_service = binance_service
    logger.info("✓ Binance service initialized")
    
    # Initialize MT5 service (forex) - only if enabled (lazy import)
    mt5_service = MT5Service()
    # MT5 initialization is async but lightweight if disabled
    await mt5_service.initialize()
    app.state.mt5_service = mt5_service
    logger.info("✓ MT5 service initialized")
    
    logger.info("✅ Backend started successfully!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NOF1 Trading Bot Backend...")
    await binance_service.close()
    await mt5_service.close()
    logger.info("✅ Backend shut down successfully!")


app = FastAPI(
    title="NOF1 Trading Bot API",
    description="AI-powered crypto trading bot with Binance integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://100.85.124.82:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(market.router, prefix="/api/market", tags=["Market Data"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(performance.router, prefix="/api/performance", tags=["Performance"])
app.include_router(ai_recommendations.router, prefix="/api/ai", tags=["AI Recommendations"])
app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info",
        # Optimize for faster startup
        access_log=False,  # Disable access logs for faster startup
        loop="asyncio",  # Use asyncio event loop (faster than uvloop on Windows)
    )

