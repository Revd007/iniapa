"""
Market Data Routes
Dynamic market overview dari database (tidak hardcode)
Fetch semua symbols dari market_symbols table
"""

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from typing import List
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import MarketSymbol, AssetClass
from app.services.market_sync_service import MarketSyncService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview")
async def get_market_overview(
    request: Request,
    asset_class: str = Query("crypto", description="crypto | forex"),
    db: Session = Depends(get_db),
):
    """
    Get market overview - dynamic dari database
    Tidak hardcode symbols, ambil dari market_symbols table
    """
    try:
        if asset_class == "forex":
            mt5_service = getattr(request.app.state, "mt5_service", None)
            if not mt5_service or not settings.MT5_ENABLED:
                raise HTTPException(status_code=503, detail="MT5 service not enabled")
            overview = await mt5_service.get_market_overview()
        else:
            # Crypto: Fetch SEMUA symbols untuk search, tapi tampilkan hanya top 5 di UI
            # User bisa search semua symbols, tapi default view hanya 5 teratas
            asset_class_enum = AssetClass.CRYPTO
            # Fetch symbols untuk search functionality
            # Limit: max 100 symbols untuk menghindari rate limit spam
            # Frontend akan filter hasil search dari data ini
            MAX_SYMBOLS_FOR_TICKER = 100  # Batasi untuk mencegah rate limit
            
            all_symbols = db.query(MarketSymbol).filter(
                MarketSymbol.asset_class == asset_class_enum,
                MarketSymbol.is_active == True
            ).order_by(MarketSymbol.volume_24h.desc()).limit(MAX_SYMBOLS_FOR_TICKER).all()
            
            # Untuk display default: hanya top 5
            # Tapi kita fetch top 100 untuk search filter di frontend (BCH, LTC, dll bisa ditemukan)
            symbols = all_symbols  # Ambil top 100 symbols untuk search (cukup untuk coverage)
            
            if not symbols:
                # Fallback: sync symbols jika belum ada
                binance_service = request.app.state.binance_service
                market_sync = MarketSyncService(binance_service)
                await market_sync.sync_crypto_symbols(db)
                # Retry query - semua symbols for search
                symbols = db.query(MarketSymbol).filter(
                    MarketSymbol.asset_class == asset_class_enum,
                    MarketSymbol.is_active == True
                ).order_by(MarketSymbol.volume_24h.desc()).all()
            
            # Fetch ticker data dari Binance menggunakan batch endpoint (lebih efisien)
            # Batch endpoint: 1 request untuk semua tickers vs 100 individual requests
            binance_service = request.app.state.binance_service
            overview = []
            
            try:
                # Get all tickers in one batch request (weight: 40, but better than 100 individual requests)
                all_tickers = await binance_service.get_24h_tickers()
                ticker_map = {t['symbol']: t for t in all_tickers} if all_tickers else {}
                
                # Process only the symbols we need
                for symbol_obj in symbols:
                    ticker = ticker_map.get(symbol_obj.symbol)
                    if not ticker:
                        continue
                    
                    try:
                        # Format symbol untuk display: "BTCUSDT" -> "BTC/USDT" (untuk konsistensi dengan frontend)
                        display_symbol = symbol_obj.symbol.replace('USDT', '/USDT')
                        price = float(ticker.get('lastPrice', 0))
                        change_pct = float(ticker.get('priceChangePercent', 0))
                        volume = float(ticker.get('quoteVolume', 0))
                        high = float(ticker.get('highPrice', 0))
                        low = float(ticker.get('lowPrice', 0))
                        
                        overview.append({
                            'symbol': display_symbol,  # Format untuk display: "BTC/USDT"
                            'raw_symbol': symbol_obj.symbol,  # Format asli: "BTCUSDT" untuk search
                            'price': f"{price:,.2f}" if price >= 1 else f"{price:.8f}".rstrip('0').rstrip('.'),
                            'change': f"{change_pct:+.2f}%",
                            'volume': f"${volume:,.0f}" if volume >= 1000 else f"${volume:.2f}",
                            'high24h': f"{high:,.2f}" if high >= 1 else f"{high:.8f}".rstrip('0').rstrip('.'),
                            'low24h': f"{low:,.2f}" if low >= 1 else f"{low:.8f}".rstrip('0').rstrip('.'),
                            'raw_price': price,
                            'raw_change': change_pct,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to process ticker for {symbol_obj.symbol}: {e}")
                        continue
                        
            except Exception as e:
                error_str = str(e)
                # Don't retry if it's a geolocation restriction - circuit breaker will handle it
                if 'geolocation restriction' in error_str.lower() or 'not available in your location' in error_str.lower():
                    logger.warning(f"Geolocation restriction detected, skipping fallback retries: {error_str}")
                    # Return empty overview instead of retrying
                    return {
                        "success": False,
                        "data": [],
                        "timestamp": None,
                        "count": 0,
                        "error": "Binance API is not available in your location due to geolocation restrictions. Please use VPN or contact support."
                    }
                
                logger.error(f"Failed to fetch batch tickers: {e}")
                # Fallback: try individual requests for top 5 only (only if not geolocation error)
                for symbol_obj in symbols[:5]:
                    try:
                        ticker = await binance_service.get_24h_ticker(symbol_obj.symbol)
                        display_symbol = symbol_obj.symbol.replace('USDT', '/USDT')
                        price = float(ticker.get('lastPrice', 0))
                        change_pct = float(ticker.get('priceChangePercent', 0))
                        volume = float(ticker.get('quoteVolume', 0))
                        high = float(ticker.get('highPrice', 0))
                        low = float(ticker.get('lowPrice', 0))
                        
                        overview.append({
                            'symbol': display_symbol,
                            'raw_symbol': symbol_obj.symbol,
                            'price': f"{price:,.2f}" if price >= 1 else f"{price:.8f}".rstrip('0').rstrip('.'),
                            'change': f"{change_pct:+.2f}%",
                            'volume': f"${volume:,.0f}" if volume >= 1000 else f"${volume:.2f}",
                            'high24h': f"{high:,.2f}" if high >= 1 else f"{high:.8f}".rstrip('0').rstrip('.'),
                            'low24h': f"{low:,.2f}" if low >= 1 else f"{low:.8f}".rstrip('0').rstrip('.'),
                            'raw_price': price,
                            'raw_change': change_pct,
                        })
                    except Exception as e2:
                        # Check if fallback also failed due to geolocation
                        if 'geolocation restriction' in str(e2).lower() or 'not available in your location' in str(e2).lower():
                            logger.warning(f"Geolocation restriction in fallback, stopping retries")
                            break
                        logger.warning(f"Failed to fetch ticker for {symbol_obj.symbol}: {e2}")
                        continue
        
        return {
            "success": True,
            "data": overview,
            "timestamp": None,
            "count": len(overview)
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

