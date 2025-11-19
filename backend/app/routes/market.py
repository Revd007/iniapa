"""
Market Data Routes
Endpoints for retrieving market overview and ticker information
"""

from fastapi import APIRouter, HTTPException, Request, Query
from typing import List
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview")
async def get_market_overview(
    request: Request,
    asset_class: str = Query("crypto", description="crypto | forex"),
):
    """Get market overview for crypto (Binance) or forex (MT5)."""
    try:
        if asset_class == "forex":
            mt5_service = getattr(request.app.state, "mt5_service", None)
            if not mt5_service or not settings.MT5_ENABLED:
                raise HTTPException(status_code=503, detail="MT5 service not enabled")
            overview = await mt5_service.get_market_overview()
        else:
            binance_service = request.app.state.binance_service
            # Get overview for supported crypto symbols
            overview = await binance_service.get_market_overview(settings.SUPPORTED_SYMBOLS)
        
        return {
            "success": True,
            "data": overview,
            "timestamp": None
        }
    except Exception as e:
        logger.error(f"Failed to get market overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str, request: Request):
    """Get ticker data for a specific symbol"""
    try:
        binance_service = request.app.state.binance_service
        
        # Ensure symbol has USDT suffix
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        ticker = await binance_service.get_24h_ticker(symbol)
        
        return {
            "success": True,
            "data": ticker
        }
    except Exception as e:
        logger.error(f"Failed to get ticker for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{symbol}")
async def get_order_book(symbol: str, limit: int = 10, request: Request = None):
    """Get order book for a symbol"""
    try:
        binance_service = request.app.state.binance_service
        
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        order_book = await binance_service.get_order_book(symbol, limit)
        
        return {
            "success": True,
            "data": order_book
        }
    except Exception as e:
        logger.error(f"Failed to get order book for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

