"""
Trading Routes
Endpoints for executing trades and managing positions
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.database import get_db, Trade
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class TradeRequest(BaseModel):
    """Trade request model"""
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"  # MARKET or LIMIT
    price: Optional[float] = None
    leverage: Optional[float] = 1.0
    trading_mode: Optional[str] = "normal"
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class CloseTradeRequest(BaseModel):
    """Close trade request model"""
    trade_id: int
    exit_price: Optional[float] = None


@router.post("/execute")
async def execute_trade(
    trade_request: TradeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Execute a trade (quick execute)"""
    try:
        binance_service = request.app.state.binance_service
        
        # Ensure symbol has USDT suffix
        symbol = trade_request.symbol
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # ALWAYS get current market price from Binance for accurate entry_price
        ticker = await binance_service.get_ticker_price(symbol)
        market_price = float(ticker.get('price', 0))
        
        # Use user-provided price for LIMIT orders, but market price for trade record
        order_price = trade_request.price if trade_request.order_type == "LIMIT" and trade_request.price else market_price
        
        # Calculate total value based on market price (for accurate position sizing)
        total_value = trade_request.quantity * market_price
        
        # Entry price for database will be the actual fill price or market price
        current_price = market_price

        binance_order_id = None
        sl_order_id: Optional[str] = None
        tp_order_id: Optional[str] = None

        # Detect paper-trading mode (config flag) or missing keys; if so, do not send real orders
        api_key = settings.BINANCE_API_KEY or ""
        paper_trading = settings.BINANCE_PAPER_TRADING or len(api_key.strip()) < 30

        if paper_trading:
            if settings.BINANCE_PAPER_TRADING:
                logger.warning("BINANCE_PAPER_TRADING=true -> running in PAPER TRADING mode (no real orders).")
            else:
                logger.warning("Binance API key missing or too short; running in PAPER TRADING mode (no real orders).")
        else:
            # Execute order on Binance
            try:
                order = await binance_service.create_order(
                    symbol=symbol,
                    side=trade_request.side,
                    order_type=trade_request.order_type,
                    quantity=trade_request.quantity,
                    price=order_price if trade_request.order_type == "LIMIT" else None,
                    stop_loss=trade_request.stop_loss,
                    take_profit=trade_request.take_profit
                )
                
                # Check if order was filled
                if order.get('status') not in ['FILLED', 'NEW']:
                    raise HTTPException(status_code=400, detail=f"Order failed: {order.get('status')}")
                
                binance_order_id = order.get('orderId')
                sl_order_id = str(order.get('stop_loss_order', {}).get('orderId')) if order.get('stop_loss_order') else None
                tp_order_id = str(order.get('take_profit_order', {}).get('orderId')) if order.get('take_profit_order') else None
                
                # Get actual fill price if available
                if 'fills' in order and len(order['fills']) > 0:
                    current_price = float(order['fills'][0]['price'])
                    total_value = trade_request.quantity * current_price
                
            except Exception as e:
                err_msg = str(e)
                # If key/permission error, gracefully fall back to paper trading instead of 500
                if "code': -2015" in err_msg or "Invalid API-key" in err_msg:
                    logger.error(f"Binance demo/live key not authorized for trading ({err_msg}). Falling back to PAPER TRADING for this order.")
                    paper_trading = True
                else:
                    logger.error(f"Binance order execution failed: {err_msg}")
                    raise HTTPException(status_code=500, detail=f"Failed to execute order on Binance: {err_msg}")
        
        # Create trade record (works both for real and paper trading)
        trade = Trade(
            symbol=symbol,
            side=trade_request.side,
            order_type=trade_request.order_type,
            quantity=trade_request.quantity,
            price=current_price,
            total_value=total_value,
            leverage=trade_request.leverage,
            entry_price=current_price,
            trading_mode=trade_request.trading_mode,
            ai_confidence=trade_request.ai_confidence,
            ai_reason=trade_request.ai_reason,
            status="OPEN",
            binance_order_id=str(binance_order_id) if binance_order_id else None,
            stop_loss=trade_request.stop_loss,
            take_profit=trade_request.take_profit,
            sl_order_id=sl_order_id,
            tp_order_id=tp_order_id,
        )
        
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        logger.info(f"Trade executed: {trade.id} - {symbol} {trade_request.side} {trade_request.quantity}")
        
        return {
            "success": True,
            "message": "Trade executed successfully",
            "trade": {
                "id": trade.id,
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "total_value": trade.total_value,
                "leverage": trade.leverage,
                "status": trade.status,
                "created_at": trade.created_at.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to execute trade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close")
async def close_trade(
    close_request: CloseTradeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Close an open trade manually (with Binance order cancellation if applicable)"""
    try:
        # Get trade from database
        trade = db.query(Trade).filter(Trade.id == close_request.trade_id).first()
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        if trade.status != "OPEN":
            raise HTTPException(status_code=400, detail="Trade is not open")
        
        binance_service = request.app.state.binance_service
        
        # Get current price if not provided
        exit_price = close_request.exit_price
        if not exit_price:
            ticker = await binance_service.get_ticker_price(trade.symbol)
            exit_price = float(ticker.get('price', 0))
        
        # Cancel SL/TP orders on Binance if they exist (before closing)
        if not settings.BINANCE_PAPER_TRADING and binance_service.api_key:
            try:
                if trade.sl_order_id:
                    await binance_service.cancel_order(trade.symbol, trade.sl_order_id)
                    logger.info(f"Cancelled SL order {trade.sl_order_id} for trade {trade.id}")
                if trade.tp_order_id:
                    await binance_service.cancel_order(trade.symbol, trade.tp_order_id)
                    logger.info(f"Cancelled TP order {trade.tp_order_id} for trade {trade.id}")
            except Exception as e:
                logger.warning(f"Failed to cancel SL/TP orders for trade {trade.id}: {e}")
                # Continue anyway - we'll still close the trade
        
        # Calculate profit/loss
        if trade.side == "BUY":
            profit_loss = (exit_price - trade.entry_price) * trade.quantity * (trade.leverage or 1)
        else:  # SELL
            profit_loss = (trade.entry_price - exit_price) * trade.quantity * (trade.leverage or 1)
        
        profit_loss_percent = (profit_loss / trade.total_value) * 100 if trade.total_value > 0 else 0
        
        # Update trade
        trade.exit_price = exit_price
        trade.profit_loss = profit_loss
        trade.profit_loss_percent = profit_loss_percent
        trade.is_win = profit_loss > 0
        trade.status = "CLOSED"
        trade.closed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(trade)
        
        logger.info(f"Trade closed manually: {trade.id} ({trade.symbol}) - P/L: ${profit_loss:.2f} ({profit_loss_percent:.2f}%)")
        
        return {
            "success": True,
            "message": "Trade closed successfully",
            "trade": {
                "id": trade.id,
                "symbol": trade.symbol,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "profit_loss": profit_loss,
                "profit_loss_percent": profit_loss_percent,
                "is_win": trade.is_win,
                "closed_at": trade.closed_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close trade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open-trades")
async def get_open_trades(db: Session = Depends(get_db)):
    """Get all open trades"""
    try:
        trades = db.query(Trade).filter(Trade.status == "OPEN").all()
        
        return {
            "success": True,
            "count": len(trades),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "leverage": t.leverage,
                    "total_value": t.total_value,
                    "created_at": t.created_at.isoformat()
                }
                for t in trades
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get open trades: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get detailed open positions banner data with auto-close TP/SL checking."""
    try:
        binance_service = request.app.state.binance_service

        trades = db.query(Trade).filter(Trade.status == "OPEN").all()

        positions = []
        auto_closed = []
        
        # Batch fetch all unique symbols for mark prices (optimize API calls)
        unique_symbols = list(set(t.symbol for t in trades))
        mark_prices_cache = {}
        
        for symbol in unique_symbols:
            try:
                ticker = await binance_service.get_ticker_price(symbol)
                mark_prices_cache[symbol] = float(ticker.get("price", 0))
            except Exception:
                mark_prices_cache[symbol] = None
        
        for t in trades:
            # Use cached mark price or fallback to entry price
            mark_price = mark_prices_cache.get(t.symbol) or t.entry_price

            # AUTO-CLOSE CHECK: Check if TP or SL is hit
            should_close = False
            close_reason = None
            
            if t.stop_loss and mark_price:
                if t.side == "BUY" and mark_price <= t.stop_loss:
                    should_close = True
                    close_reason = "Stop Loss"
                elif t.side == "SELL" and mark_price >= t.stop_loss:
                    should_close = True
                    close_reason = "Stop Loss"
            
            if t.take_profit and mark_price:
                if t.side == "BUY" and mark_price >= t.take_profit:
                    should_close = True
                    close_reason = "Take Profit"
                elif t.side == "SELL" and mark_price <= t.take_profit:
                    should_close = True
                    close_reason = "Take Profit"
            
            # Auto-close if TP/SL hit
            if should_close:
                try:
                    # Calculate profit/loss
                    if t.side == "BUY":
                        profit_loss = (mark_price - t.entry_price) * t.quantity * (t.leverage or 1)
                    else:  # SELL
                        profit_loss = (t.entry_price - mark_price) * t.quantity * (t.leverage or 1)
                    
                    profit_loss_percent = (profit_loss / t.total_value) * 100 if t.total_value else 0
                    
                    # Update trade
                    t.exit_price = mark_price
                    t.profit_loss = profit_loss
                    t.profit_loss_percent = profit_loss_percent
                    t.is_win = profit_loss > 0
                    t.status = "CLOSED"
                    t.closed_at = datetime.utcnow()
                    
                    # Try to cancel SL/TP orders on Binance if they exist
                    if not settings.BINANCE_PAPER_TRADING and binance_service.api_key:
                        try:
                            if t.sl_order_id:
                                await binance_service.cancel_order(t.symbol, t.sl_order_id)
                            if t.tp_order_id:
                                await binance_service.cancel_order(t.symbol, t.tp_order_id)
                        except Exception as e:
                            logger.warning(f"Failed to cancel SL/TP orders for trade {t.id}: {e}")
                    
                    db.commit()
                    logger.info(f"Auto-closed trade {t.id} ({t.symbol}) - {close_reason} at ${mark_price:.2f}, P/L: ${profit_loss:.2f}")
                    auto_closed.append({"id": t.id, "symbol": t.symbol, "reason": close_reason})
                    continue  # Skip adding to positions list
                except Exception as e:
                    logger.error(f"Failed to auto-close trade {t.id}: {e}")
                    db.rollback()

            size = t.quantity
            entry_price = t.entry_price
            break_even_price = entry_price  # simplified

            # Unrealized PnL
            if t.side == "BUY":
                pnl = (mark_price - entry_price) * size * (t.leverage or 1)
            else:
                pnl = (entry_price - mark_price) * size * (t.leverage or 1)

            roi_percent = (pnl / t.total_value * 100) if t.total_value else 0

            # Simple margin approximation
            margin = t.total_value / (t.leverage or 1)
            margin_ratio = abs(pnl) / margin * 100 if margin else 0

            positions.append(
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "size": size,
                    "entry_price": entry_price,
                    "break_even_price": break_even_price,
                    "mark_price": mark_price,
                    "liq_price": None,  # can be extended with real formula later
                    "margin_ratio": margin_ratio,
                    "margin": margin,
                    "pnl": pnl,
                    "roi_percent": roi_percent,
                    "est_funding_fee": 0.0,
                    "leverage": t.leverage,
                    "stop_loss": t.stop_loss,
                    "take_profit": t.take_profit,
                    "created_at": t.created_at.isoformat(),
                }
            )

        return {
            "success": True,
            "count": len(positions),
            "positions": positions,
            "auto_closed": auto_closed,  # Inform frontend about auto-closed positions
        }

    except Exception as e:
        logger.error(f"Failed to get positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trade-history")
async def get_trade_history(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get trade history"""
    try:
        trades = db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "count": len(trades),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "profit_loss": t.profit_loss,
                    "profit_loss_percent": t.profit_loss_percent,
                    "is_win": t.is_win,
                    "status": t.status,
                    "leverage": t.leverage,
                    "trading_mode": t.trading_mode,
                    "created_at": t.created_at.isoformat(),
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None
                }
                for t in trades
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get trade history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

