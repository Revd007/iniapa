"""
Trading Routes
Endpoints for executing trades and managing positions
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging

from app.database import get_db, Trade
from app.config import settings
from app.services.binance_service import BinanceService

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
    execution_mode: Optional[str] = "demo"  # demo or live
    user_id: Optional[int] = 1
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
    """
    Execute trade dengan dual-mode support:
    - demo: Paper trading, tidak hit Binance API, track di DB
    - live: OAuth-authenticated, real trading (coming soon)
    """
    try:
        from app.models import TradeMode
        from app.services.demo_account_service import DemoAccountService
        
        binance_service = request.app.state.binance_service
        
        # Determine execution mode
        execution_mode = TradeMode.DEMO if trade_request.execution_mode == "demo" else TradeMode.LIVE
        user_id = trade_request.user_id or 1
        
        # Ensure symbol has USDT suffix
        symbol = trade_request.symbol
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # ALWAYS get current market price from Binance
        ticker = await binance_service.get_ticker_price(symbol)
        market_price = float(ticker.get('price', 0))
        
        # Calculate total value
        total_value = trade_request.quantity * market_price
        
        # Check margin availability for demo mode
        if execution_mode == TradeMode.DEMO:
            can_trade, reason = DemoAccountService.can_open_trade(
                db, 
                user_id,
                trade_request.quantity,
                market_price,
                trade_request.leverage or 1.0
            )
            if not can_trade:
                raise HTTPException(status_code=400, detail=reason)
        
        # Entry price
        current_price = market_price
        binance_order_id = None
        sl_order_id: Optional[str] = None
        tp_order_id: Optional[str] = None
        
        # Determine if we should execute real order to Binance
        # Execute to Binance if:
        # 1. Not in paper trading mode (BINANCE_PAPER_TRADING = false)
        # 2. Has valid API keys (either demo or live keys)
        # 3. Binance service is configured
        paper_trading = settings.BINANCE_PAPER_TRADING
        has_api_keys = bool(binance_service.api_key and binance_service.api_secret and len(binance_service.api_key) > 10)
        
        should_execute_binance = not paper_trading and has_api_keys and binance_service
        
        if should_execute_binance:
            # Execute real order to Binance (Demo Testnet or Live)
            try:
                logger.info(f"🚀 Executing real order to Binance {'TESTNET' if settings.BINANCE_TESTNET else 'LIVE'}: {symbol} {trade_request.side}")
                
                # Use Futures API for Futures trading (preferred)
                # Try Futures first, fallback to Spot if Futures fails
                order_response = None
                try:
                    logger.info(f"🔄 Attempting Futures order...")
                    order_response = await binance_service.create_futures_order(
                        symbol=symbol,
                        side=trade_request.side,
                        order_type=trade_request.order_type,
                        quantity=trade_request.quantity,
                        price=trade_request.price if trade_request.order_type == "LIMIT" else None,
                        stop_loss=trade_request.stop_loss,
                        take_profit=trade_request.take_profit,
                        position_side="BOTH"
                    )
                    logger.info("✅ Futures order executed successfully")
                except Exception as futures_error:
                    logger.warning(f"⚠️ Futures order failed: {futures_error}, falling back to Spot order...")
                    # Fallback to Spot order
                    order_response = await binance_service.create_order(
                    symbol=symbol,
                    side=trade_request.side,
                    order_type=trade_request.order_type,
                    quantity=trade_request.quantity,
                    price=trade_request.price if trade_request.order_type == "LIMIT" else None,
                    stop_loss=trade_request.stop_loss,
                    take_profit=trade_request.take_profit
                )
                    logger.info("✅ Futures order executed successfully")
                
                # Handle order response structure
                main_order = order_response.get('main_order', order_response)
                
                # Extract order ID from response
                binance_order_id = main_order.get('orderId') or main_order.get('orderId')
                
                # Extract SL/TP order IDs if they exist
                if 'stop_loss_order' in order_response:
                    sl_order_id = str(order_response['stop_loss_order'].get('orderId', ''))
                if 'take_profit_order' in order_response:
                    tp_order_id = str(order_response['take_profit_order'].get('orderId', ''))
                
                # Get actual fill price if available
                if 'fills' in main_order and len(main_order['fills']) > 0:
                    current_price = float(main_order['fills'][0]['price'])
                    total_value = trade_request.quantity * current_price
                elif 'price' in main_order:
                    current_price = float(main_order['price'])
                
                logger.info(f"✅ Binance order executed: OrderID={binance_order_id}, Price=${current_price:.2f}")
                
            except Exception as e:
                err_msg = str(e)
                logger.error(f"❌ Failed to execute order to Binance: {err_msg}")
                
                # If key/permission error, gracefully fall back to paper trading
                if "code': -2015" in err_msg or "Invalid API-key" in err_msg or "code': -1022" in err_msg:
                    logger.warning("⚠️ Binance API key not authorized for trading. Falling back to PAPER TRADING mode.")
                    paper_trading = True
                    should_execute_binance = False
                else:
                    # For other errors, raise exception (might be temporary issue)
                    raise HTTPException(status_code=500, detail=f"Failed to execute order on Binance: {err_msg}")
        else:
            # Paper trading mode: simulation only
            if paper_trading:
                logger.info(f"📝 Paper trading mode: Simulating trade for {symbol} @ ${market_price} (no real Binance order)")
            elif not has_api_keys:
                logger.info(f"📝 No API keys configured: Simulating trade for {symbol} @ ${market_price} (no real Binance order)")
            else:
                logger.info(f"📝 Demo mode: Simulating trade for {symbol} @ ${market_price}")
        
        # Create trade record in database
        trade = Trade(
            user_id=user_id,
            symbol=symbol,
            side=trade_request.side,
            order_type=trade_request.order_type,
            quantity=trade_request.quantity,
            price=current_price,
            total_value=total_value,
            leverage=trade_request.leverage,
            entry_price=current_price,
            trading_mode=trade_request.trading_mode,
            execution_mode=execution_mode,  # demo or live
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
        
        mode_label = "DEMO" if execution_mode == TradeMode.DEMO else "LIVE"
        logger.info(f"Trade executed [{mode_label}]: {trade.id} - {symbol} {trade_request.side} {trade_request.quantity} @ ${current_price}")
        
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
    """Close an open trade manually and close position on Binance Futures if live"""
    try:
        from app.models import TradeMode, APICredential
        from app.services.binance_service import BinanceService
        
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
        
        # Check if this is a LIVE trade that needs to be closed on Binance
        if trade.execution_mode == TradeMode.LIVE and not settings.BINANCE_PAPER_TRADING:
            logger.info(f"🔴 Closing LIVE position on Binance Futures for trade {trade.id}")
            
            # Get API credentials from database
            api_creds = db.query(APICredential).filter_by(user_id=trade.user_id).first()
            
            if api_creds and api_creds.binance_api_key and api_creds.binance_api_secret:
                try:
                    # Decrypt API keys
                    from cryptography.fernet import Fernet
                    import base64
                    import hashlib
                    encryption_key = base64.urlsafe_b64encode(hashlib.sha256(b"nof1trading_secret_key").digest())
                    cipher = Fernet(encryption_key)
                    
                    api_key = cipher.decrypt(api_creds.binance_api_key.encode()).decode()
                    api_secret = cipher.decrypt(api_creds.binance_api_secret.encode()).decode()
                    
                    # Create BinanceService instance for live trading
                    live_binance_service = BinanceService()
                    live_binance_service.api_key = api_key
                    live_binance_service.api_secret = api_secret
                    live_binance_service.testnet = False  # Live mode
                    live_binance_service.base_url = "https://api.binance.com/api"
                    await live_binance_service.initialize()
                    
                    try:
                        # Cancel SL/TP orders FIRST (Futures uses different endpoints)
                        # Use sl_order_id and tp_order_id (not binance_sl_order_id)
                        if trade.sl_order_id or trade.tp_order_id:
                            try:
                                if trade.sl_order_id:
                                    # Cancel Futures order
                                    await live_binance_service.cancel_futures_order(trade.symbol, int(trade.sl_order_id))
                                    logger.info(f"✅ Cancelled Futures SL order {trade.sl_order_id}")
                                if trade.tp_order_id:
                                    await live_binance_service.cancel_futures_order(trade.symbol, int(trade.tp_order_id))
                                    logger.info(f"✅ Cancelled Futures TP order {trade.tp_order_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to cancel SL/TP orders: {e}")
                        
                        # Close position by placing REVERSE order (BUY -> SELL, SELL -> BUY)
                        close_side = "SELL" if trade.side == "BUY" else "BUY"
                        
                        logger.info(f"📤 Executing Futures CLOSE order: {close_side} {trade.quantity} {trade.symbol} @ market")
                        
                        # Execute close order on Binance Futures
                        close_order = await live_binance_service.create_futures_order(
                            symbol=trade.symbol,
                            side=close_side,
                            order_type="MARKET",
                            quantity=trade.quantity,
                            position_side="BOTH"
                        )
                        
                        # Extract executed price from response
                        main_order = close_order.get('main_order', close_order)
                        if 'avgPrice' in main_order:
                            exit_price = float(main_order['avgPrice'])
                        
                        logger.info(f"✅ Position closed on Binance Futures: OrderID={main_order.get('orderId')}, Price=${exit_price}")
                    
                    finally:
                        # Always close the BinanceService session, even if there's an error
                        await live_binance_service.close()
                    
                except Exception as e:
                    logger.error(f"❌ Failed to close position on Binance Futures: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to close position on Binance: {str(e)}")
            else:
                logger.warning(f"⚠️ No API credentials found for user {trade.user_id} - cannot close position on Binance")
        
        # For DEMO trades or if Binance close succeeded, also cancel any remaining SL/TP
        elif binance_service.api_key and (trade.sl_order_id or trade.tp_order_id):
            try:
                if trade.sl_order_id:
                    await binance_service.cancel_order(trade.symbol, trade.sl_order_id)
                    logger.info(f"Cancelled SL order {trade.sl_order_id} for demo trade {trade.id}")
                if trade.tp_order_id:
                    await binance_service.cancel_order(trade.symbol, trade.tp_order_id)
                    logger.info(f"Cancelled TP order {trade.tp_order_id} for demo trade {trade.id}")
            except Exception as e:
                logger.warning(f"Failed to cancel demo SL/TP orders for trade {trade.id}: {e}")
        
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
        trade.closed_at = datetime.now(timezone.utc)
        
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
    env: str = "demo",  # demo or live
    db: Session = Depends(get_db),
):
    """Get detailed open positions banner data with auto-close TP/SL checking."""
    try:
        from app.models import TradeMode
        
        binance_service = request.app.state.binance_service

        # Normalize env (accept aliases)
        env = env.lower()
        if env == "production":
            env = "live"
        elif env == "simulation":
            env = "demo"  # simulation is alias for demo
        
        # Filter by execution_mode (demo/live)
        execution_mode = TradeMode.DEMO if env == "demo" else TradeMode.LIVE

        trades = db.query(Trade).filter(
            Trade.status == "OPEN",
            Trade.execution_mode == execution_mode
        ).all()
        
        logger.info(f"📊 Fetching positions for env={env}, execution_mode={execution_mode.value}, found={len(trades)} trades")
        
        # Temporary fix: If requesting LIVE but no trades found, also check DEMO
        # This helps during migration from DEMO to LIVE
        if env == "live" and len(trades) == 0:
            logger.info("⚠️ No LIVE trades found, checking DEMO trades as fallback...")
            demo_trades = db.query(Trade).filter(
                Trade.status == "OPEN",
                Trade.execution_mode == TradeMode.DEMO
            ).all()
            
            if demo_trades:
                logger.warning(f"Found {len(demo_trades)} OPEN trades in DEMO mode - auto-migrating to LIVE")
                # Auto-migrate these trades to LIVE
                for trade in demo_trades:
                    trade.execution_mode = TradeMode.LIVE
                    logger.info(f"  Migrated {trade.symbol} to LIVE mode")
                db.commit()
                trades = demo_trades  # Use the migrated trades

        positions = []
        auto_closed = []
        
        # For LIVE trades, fetch ACTUAL position data from Binance Futures API
        binance_positions = {}  # symbol -> position data from Binance
        if env == "live" and execution_mode == TradeMode.LIVE:
            try:
                from app.models import APICredential
                
                api_creds = db.query(APICredential).filter_by(user_id=1).first()  # TODO: Get from auth context
                
                if api_creds and api_creds.binance_api_key and api_creds.binance_api_secret:
                    # Decrypt API keys
                    from cryptography.fernet import Fernet
                    import base64
                    import hashlib
                    encryption_key = base64.urlsafe_b64encode(hashlib.sha256(b"nof1trading_secret_key").digest())
                    cipher = Fernet(encryption_key)
                    
                    api_key = cipher.decrypt(api_creds.binance_api_key.encode()).decode()
                    api_secret = cipher.decrypt(api_creds.binance_api_secret.encode()).decode()
                    
                    # Create BinanceService instance for live trading
                    live_binance_service = BinanceService()
                    live_binance_service.api_key = api_key
                    live_binance_service.api_secret = api_secret
                    live_binance_service.testnet = False
                    live_binance_service.base_url = "https://api.binance.com/api"
                    await live_binance_service.initialize()
                    
                    try:
                        # Fetch actual positions from Binance Futures
                        futures_account = await live_binance_service.get_futures_account_info()
                        
                        # Parse positions from Binance response
                        for position in futures_account.get('positions', []):
                            symbol = position.get('symbol')
                            position_amt = float(position.get('positionAmt', 0))
                            
                            # Only include positions with non-zero amount
                            if abs(position_amt) > 0:
                                binance_positions[symbol] = {
                                    'positionAmt': position_amt,
                                    'entryPrice': float(position.get('entryPrice', 0)),
                                    'markPrice': float(position.get('markPrice', 0)),
                                    'unRealizedProfit': float(position.get('unRealizedProfit', 0)),
                                    'leverage': int(position.get('leverage', 1)),
                                    'marginType': position.get('marginType', 'CROSSED'),
                                    'isolatedMargin': float(position.get('isolatedMargin', 0)),
                                    'notional': float(position.get('notional', 0))
                                }
                                logger.info(f"📊 Binance position for {symbol}: Entry=${position.get('entryPrice')}, Mark=${position.get('markPrice')}, PNL=${position.get('unRealizedProfit')}")
                    
                    finally:
                        # Always close the BinanceService session, even if there's an error
                        await live_binance_service.close()
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch Binance positions: {e} - using database data")
        
        # Batch fetch all unique symbols for mark prices (optimize API calls)
        unique_symbols = list(set(t.symbol for t in trades))
        mark_prices_cache = {}
        
        for symbol in unique_symbols:
            # For LIVE trades, use Binance mark price if available
            if symbol in binance_positions:
                mark_prices_cache[symbol] = binance_positions[symbol]['markPrice']
            # else:
            try:
                ticker = await binance_service.get_ticker_price(symbol)
                mark_prices_cache[symbol] = float(ticker.get("price", 0))
            except Exception:
                mark_prices_cache[symbol] = None
        
        for t in trades:
            # Use cached mark price or fallback to entry price
            mark_price = mark_prices_cache.get(t.symbol) or t.entry_price

            # COOLDOWN PERIOD: Don't auto-close trades that are less than 10 seconds old
            # This prevents immediate auto-close due to price fluctuations right after execution
            # Both datetimes are timezone-aware: created_at from DB (DateTime(timezone=True)) and now_utc
            now_utc = datetime.now(timezone.utc)
            trade_age_seconds = (now_utc - t.created_at).total_seconds()
            if trade_age_seconds < 10:
                # Trade too new, skip auto-close check
                logger.debug(f"Trade {t.id} too new ({trade_age_seconds:.1f}s), skipping auto-close check")
                # Still add to positions list below
            else:
                # AUTO-CLOSE CHECK: Check if TP or SL is hit (only for trades older than 10 seconds)
                should_close = False
                close_reason = None
                
                # Minimum distance buffer: TP/SL must be at least 0.5% away from entry price
                min_distance_percent = 0.5
                min_distance = t.entry_price * (min_distance_percent / 100)
                
                if t.stop_loss and mark_price:
                    # Validate SL distance from entry
                    sl_distance = abs(t.stop_loss - t.entry_price)
                    if sl_distance < min_distance:
                        logger.warning(f"Trade {t.id} has SL too close to entry ({sl_distance:.2f} < {min_distance:.2f}), ignoring SL")
                    else:
                        if t.side == "BUY" and mark_price <= t.stop_loss:
                            should_close = True
                            close_reason = "Stop Loss"
                        elif t.side == "SELL" and mark_price >= t.stop_loss:
                            should_close = True
                            close_reason = "Stop Loss"
                
                if t.take_profit and mark_price:
                    # Validate TP distance from entry
                    tp_distance = abs(t.take_profit - t.entry_price)
                    if tp_distance < min_distance:
                        logger.warning(f"Trade {t.id} has TP too close to entry ({tp_distance:.2f} < {min_distance:.2f}), ignoring TP")
                    else:
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
                        t.closed_at = datetime.now(timezone.utc)
                        
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

            # Continue to add position to list (if not auto-closed)
            # For LIVE trades, use ACTUAL data from Binance if available
            if t.symbol in binance_positions:
                binance_pos = binance_positions[t.symbol]
                
                # Use ACTUAL entry price, mark price, and PNL from Binance
                entry_price = binance_pos['entryPrice']
                mark_price = binance_pos['markPrice']
                pnl = binance_pos['unRealizedProfit']
                size = abs(binance_pos['positionAmt'])
                actual_leverage = binance_pos['leverage']
                actual_margin = binance_pos['isolatedMargin'] if binance_pos['marginType'] == 'ISOLATED' else (binance_pos['notional'] / actual_leverage)
                
                # Update database with actual entry price from Binance (sync)
                if abs(t.entry_price - entry_price) > 0.01:  # Only update if significantly different
                    logger.info(f"🔄 Syncing entry price for {t.symbol}: DB={t.entry_price} -> Binance={entry_price}")
                    t.entry_price = entry_price
                    db.commit()
                
                # Calculate ROI based on actual margin used
                roi_percent = (pnl / actual_margin * 100) if actual_margin > 0 else 0
                margin_ratio = abs(pnl) / actual_margin * 100 if actual_margin > 0 else 0
                
                logger.info(f"✅ Using Binance data for {t.symbol}: Entry=${entry_price}, Mark=${mark_price}, PNL=${pnl:.2f}, ROI={roi_percent:.2f}%")
            else:
                # For DEMO trades or if Binance data not available, use database data
                size = t.quantity
                entry_price = t.entry_price
                mark_price = mark_prices_cache.get(t.symbol) or t.entry_price
                actual_leverage = t.leverage or 1

                # Calculate margin (same as Binance: total_value / leverage)
                actual_margin = t.total_value / actual_leverage if t.total_value and actual_leverage > 0 else 0

                # Unrealized PnL (same formula as Binance)
                if t.side == "BUY":
                    pnl = (mark_price - entry_price) * size
                else:
                    pnl = (entry_price - mark_price) * size
                    
                # Apply leverage to PnL
                pnl = pnl * actual_leverage

                # ROI based on margin (same as LIVE trades) - FIXED to match Binance
                roi_percent = (pnl / actual_margin * 100) if actual_margin > 0 else 0
                margin_ratio = abs(pnl) / actual_margin * 100 if actual_margin > 0 else 0
                
                logger.info(f"✅ Using DB data for {t.symbol}: Entry=${entry_price:.2f}, Mark=${mark_price:.2f}, PNL=${pnl:.2f}, Margin=${actual_margin:.2f}, ROI={roi_percent:.2f}%")

            positions.append(
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "size": size,
                    "entry_price": entry_price,
                    "break_even_price": entry_price,  # simplified
                    "mark_price": mark_price,
                    "liq_price": None,  # can be extended with real formula later
                    "margin_ratio": margin_ratio,
                    "margin": actual_margin,
                    "pnl": pnl,
                    "roi_percent": roi_percent,
                    "est_funding_fee": 0.0,
                    "leverage": actual_leverage,
                    "stop_loss": t.stop_loss,
                    "take_profit": t.take_profit,
                    "created_at": t.created_at.isoformat(),
                    "trading_mode": t.trading_mode.value if t.trading_mode else None,
                    "ai_confidence": t.ai_confidence,
                    "ai_reason": t.ai_reason
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

@router.post("/update-execution-mode")
async def update_execution_mode(
    from_mode: str = "demo",
    to_mode: str = "live",
    db: Session = Depends(get_db)
):
    """Update execution_mode for all OPEN trades (admin utility)"""
    try:
        from app.models import TradeMode
        
        from_execution_mode = TradeMode.DEMO if from_mode == "demo" else TradeMode.LIVE
        to_execution_mode = TradeMode.DEMO if to_mode == "demo" else TradeMode.LIVE
        
        # Find all OPEN trades with from_mode
        trades = db.query(Trade).filter(
            Trade.status == "OPEN",
            Trade.execution_mode == from_execution_mode
        ).all()
        
        logger.info(f"📊 Updating {len(trades)} OPEN trades from {from_mode} to {to_mode}")
        
        for trade in trades:
            trade.execution_mode = to_execution_mode
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Updated {len(trades)} trades from {from_mode} to {to_mode}",
            "count": len(trades)
        }
    except Exception as e:
        logger.error(f"Failed to update execution mode: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trade-history")
async def get_trade_history(
    limit: int = 50,
    env: str = "demo",  # demo or live
    db: Session = Depends(get_db)
):
    """Get trade history"""
    try:
        from app.models import TradeMode
        
        # Normalize env (accept aliases)
        env = env.lower()
        if env == "production":
            env = "live"
        elif env == "simulation":
            env = "demo"  # simulation is alias for demo
        
        # Filter by execution_mode (demo/live)
        execution_mode = TradeMode.DEMO if env == "demo" else TradeMode.LIVE
        
        trades = db.query(Trade).filter(
            Trade.execution_mode == execution_mode
        ).order_by(Trade.created_at.desc()).limit(limit).all()
        
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
                    "trading_mode": t.trading_mode.value if t.trading_mode else None,
                    "ai_confidence": t.ai_confidence,
                    "ai_reason": t.ai_reason,
                    "ai_model": t.ai_model,
                    "created_at": t.created_at.isoformat(),
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None
                }
                for t in trades
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get trade history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

