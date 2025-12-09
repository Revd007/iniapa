"""
AI Recommendations Routes
Endpoints for AI-powered trading recommendations using Qwen
Hanya analyze symbols yang ada di market overview (top 5) untuk efisiensi token
"""

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.services.ai_service import AIRecommendationService
from app.services.ai_provider_service import AIProviderManager
from app.config import settings
from app.database import get_db
from app.models import Trade, MarketSymbol, AssetClass

logger = logging.getLogger(__name__)

router = APIRouter()
ai_service = AIRecommendationService()  # Keep for backward compatibility


@router.get("/recommendations")
async def get_ai_recommendations(
    request: Request,
    mode: str = Query("normal", description="Trading mode: scalper, normal, aggressive, longhold"),
    asset_class: str = Query("crypto", description="Asset class: crypto, stocks, forex"),
    limit: int = Query(6, description="Number of recommendations", ge=1, le=12),
    ai_model: str = Query("qwen", description="AI model: qwen (deepseek deprecated)"),
    pinned_symbols: Optional[str] = Query(None, description="Comma-separated list of pinned symbols (e.g., 'BTC/USDT,ETH/USDT')"),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered trading recommendations
    NOW: Follows user's pinned symbols from market overview!
    
    If pinned_symbols provided: AI analyzes ONLY those symbols
    If no pinned_symbols: Falls back to top 5 by volume
    
    Modes:
    - scalper: 1-5min timeframe, very high risk, 5-10x leverage
    - normal: 30min-4H timeframe, medium risk, 1-5x leverage
    - aggressive: 15min-1H timeframe, very high risk, 5-15x leverage
    - longhold: Daily-Monthly timeframe, low risk, 1-2x leverage
    
    AI Models:
    - qwen: Advanced reasoning, multi-perspective analysis (default)
    """
    try:
        # Validate mode
        valid_modes = ["scalper", "normal", "aggressive", "longhold"]
        if mode not in valid_modes:
            raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {valid_modes}")
        
        # Get symbols to analyze
        if asset_class == "crypto":
            asset_class_enum = AssetClass.CRYPTO
            
            # PRIORITIZE USER'S PINNED SYMBOLS!
            if pinned_symbols:
                # Parse pinned symbols (e.g., "BTC/USDT,ETH/USDT" -> ["BTCUSDT", "ETHUSDT"])
                pinned_list = [
                    s.strip().replace('/USDT', '').replace('/USD', '').upper() + 'USDT' 
                    for s in pinned_symbols.split(',') 
                    if s.strip()
                ]
                
                # Get MarketSymbol objects for pinned symbols
                symbol_objs = db.query(MarketSymbol).filter(
                    MarketSymbol.asset_class == asset_class_enum,
                    MarketSymbol.is_active == True,
                    MarketSymbol.symbol.in_(pinned_list)
                ).all()
                
                logger.info(f"AI analyzing user's pinned symbols: {[s.symbol for s in symbol_objs]}")
            else:
                # Fallback: top 5 by volume (old behavior)
                symbol_objs = db.query(MarketSymbol).filter(
                MarketSymbol.asset_class == asset_class_enum,
                MarketSymbol.is_active == True
                ).order_by(MarketSymbol.volume_24h.desc()).limit(5).all()
                
                logger.info(f"AI analyzing top 5 symbols by volume: {[s.symbol for s in symbol_objs]}")
            
            if not symbol_objs:
                raise HTTPException(status_code=404, detail="No active crypto symbols found. Please sync market first.")
            
            # Fetch ticker data untuk top 5 symbols
            binance_service = request.app.state.binance_service
            market_data = []
            
            for symbol_obj in symbol_objs:
                try:
                    ticker = await binance_service.get_24h_ticker(symbol_obj.symbol)
                    market_data.append({
                        'symbol': symbol_obj.symbol.replace('USDT', '/USD'),
                        'price': ticker.get('lastPrice', '0'),
                        'change': ticker.get('priceChangePercent', '0'),
                        'volume': ticker.get('quoteVolume', '0'),
                        'high24h': ticker.get('highPrice', '0'),
                        'low24h': ticker.get('lowPrice', '0'),
                        'raw_price': float(ticker.get('lastPrice', 0)),
                        'raw_change': float(ticker.get('priceChangePercent', 0))
                    })
                except Exception as e:
                    logger.warning(f"Failed to fetch ticker for {symbol_obj.symbol}: {e}")
                    continue
            
            if not market_data:
                raise HTTPException(status_code=404, detail="No market data available for top symbols")
        else:
            # Forex/Stocks: belum di-implement (akan di-update nanti)
            raise HTTPException(status_code=501, detail=f"AI recommendations for {asset_class} not yet implemented")

        # Build simple RAG context from recent trade history (memory)
        recent_trades = (
            db.query(Trade)
            .order_by(Trade.created_at.desc())
            .limit(50)
            .all()
        )

        history_context_lines: list[str] = []
        if recent_trades:
            wins = sum(1 for t in recent_trades if t.is_win)
            losses = sum(1 for t in recent_trades if t.is_win is False)
            total_pl = sum((t.profit_loss or 0) for t in recent_trades)
            history_context_lines.append(
                f"Recent {len(recent_trades)} trades: {wins} wins / {losses} losses, net PnL: {total_pl:.2f} USD."
            )
            # Add per-symbol summary (top 5)
            by_symbol: dict[str, dict[str, float]] = {}
            for t in recent_trades:
                by_symbol.setdefault(t.symbol, {"trades": 0, "pnl": 0.0})
                by_symbol[t.symbol]["trades"] += 1
                by_symbol[t.symbol]["pnl"] += float(t.profit_loss or 0)

            top_symbols = sorted(
                by_symbol.items(), key=lambda kv: abs(kv[1]["pnl"]), reverse=True
            )[:5]
            for sym, stats in top_symbols:
                history_context_lines.append(
                    f"- {sym}: {int(stats['trades'])} trades, total PnL {stats['pnl']:.2f} USD."
                )

        history_context = "\n".join(history_context_lines)
        
        # Use AIProviderManager (database-driven config) with fallback to old service
        user_id = 1  # TODO: Get from auth/session
        provider_used = "legacy"
        
        try:
            # Try using new AIProviderManager (database config)
            provider_manager = AIProviderManager(user_id)
            recommendations, provider_used = await provider_manager.generate_recommendations(
                mode=mode,
                market_data=market_data,
                asset_class=asset_class,
                limit=limit,
                history_context=history_context
            )
            
            if not recommendations:
                # Fallback to old service if new system returns empty
                logger.warning("AIProviderManager returned empty, falling back to old AI service")
                recommendations = await ai_service.generate_recommendations(
                    mode=mode,
                    market_data=market_data,
                    asset_class=asset_class,
                    technical_data=None,
                    limit=limit,
                    history_context=history_context,
                    ai_model=ai_model,
                )
                provider_used = "legacy"
        except Exception as e:
            # Fallback to old service on error
            logger.warning(f"AIProviderManager error: {e}, falling back to old AI service")
            try:
                recommendations = await ai_service.generate_recommendations(
                    mode=mode,
                    market_data=market_data,
                    asset_class=asset_class,
                    technical_data=None,
                    limit=limit,
                    history_context=history_context,
                    ai_model=ai_model,
                )
                provider_used = "legacy"
            except Exception as e2:
                logger.error(f"Both AIProviderManager and legacy service failed: {e2}")
                recommendations = []
                provider_used = "fallback"
        
        return {
            "success": True,
            "mode": mode,
            "asset_class": asset_class,
            "ai_model": ai_model,
            "provider_used": provider_used,  # 'openrouter', 'agentrouter', 'legacy', or 'fallback'
            "recommendations": recommendations,
            "market_context": market_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate AI recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_trade(
    request: Request,
    symbol: str,
    mode: str = "normal"
):
    """Analyze a specific trade opportunity with AI"""
    try:
        binance_service = request.app.state.binance_service
        
        # Ensure symbol has USDT suffix
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Get detailed market data for the symbol
        ticker = await binance_service.get_24h_ticker(symbol)
        klines = await binance_service.get_klines(symbol, "1h", 24)
        
        # Format data for AI analysis
        market_data = [{
            "symbol": symbol.replace("USDT", "/USD"),
            "price": ticker.get('lastPrice', '0'),
            "change": ticker.get('priceChangePercent', '0'),
            "volume": ticker.get('volume', '0'),
            "high24h": ticker.get('highPrice', '0'),
            "low24h": ticker.get('lowPrice', '0'),
            "raw_price": float(ticker.get('lastPrice', 0)),
            "raw_change": float(ticker.get('priceChangePercent', 0))
        }]
        
        # Generate single recommendation (still leveraging technical/historical context later if needed)
        recommendations = await ai_service.generate_recommendations(
            mode=mode,
            market_data=market_data,
            asset_class="crypto",
            technical_data=None,
            limit=3,
            history_context=None,
        )
        
        return {
            "success": True,
            "symbol": symbol,
            "analysis": recommendations[0] if recommendations else None,
            "market_data": ticker
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze trade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

