"""
Robot Trading Service - Automated Trading Logic
Scans market, gets AI recommendations, executes trades based on configuration
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models import RobotConfig, Trade, TradingMode, AssetClass, TradeSide, TradeStatus
from app.services.binance_service import BinanceService
from app.database import get_db_context

logger = logging.getLogger(__name__)


class RobotTradingService:
    """
    Robot Trading Service - Automated execution based on AI recommendations
    
    Features:
    - Scheduler: Scans market every X seconds
    - AI Integration: Fetches recommendations from AI service
    - Trade Execution: Executes trades if confidence > threshold
    - Safety Checks: Max positions, max loss, cooldown
    """
    
    def __init__(self):
        self.running = False
        self.scan_task: Optional[asyncio.Task] = None
        self.binance_service: Optional[BinanceService] = None
    
    def set_binance_service(self, binance_service: BinanceService):
        """Set the Binance service instance"""
        self.binance_service = binance_service
    
    async def start(self, user_id: int = 1):
        """Start the robot trading scheduler"""
        if self.running:
            logger.warning("Robot is already running")
            return {"success": False, "message": "Robot is already running"}
        
        logger.info(f"🤖 Starting robot trading for user {user_id}")
        self.running = True
        
        # Start background scan task
        self.scan_task = asyncio.create_task(self._scan_loop(user_id))
        
        return {"success": True, "message": "Robot started successfully"}
    
    async def stop(self, user_id: int = 1):
        """Stop the robot trading scheduler and update database"""
        if not self.running:
            logger.warning("Robot is not running")
            # Still update database to ensure enabled=False
            with get_db_context() as db:
                config = db.query(RobotConfig).filter_by(user_id=user_id).first()
                if config:
                    config.enabled = False
                    db.commit()
            return {"success": False, "message": "Robot is not running"}
        
        logger.info(f"🛑 Stopping robot trading for user {user_id}")
        self.running = False
        
        # Update database to ensure enabled=False
        with get_db_context() as db:
            config = db.query(RobotConfig).filter_by(user_id=user_id).first()
            if config:
                config.enabled = False
                db.commit()
                logger.info(f"✅ Updated robot config: enabled=False for user {user_id}")
        
        # Cancel and wait for scan task to finish
        if self.scan_task:
            logger.info("Cancelling scan task...")
            self.scan_task.cancel()
            try:
                await self.scan_task
            except asyncio.CancelledError:
                logger.info("Scan task cancelled successfully")
            self.scan_task = None
        
        logger.info("✅ Robot stopped successfully")
        return {"success": True, "message": "Robot stopped successfully", "enabled": False}
    
    async def _scan_loop(self, user_id: int):
        """Main loop that scans market and executes trades"""
        try:
            while self.running:
                # Double-check if robot is still enabled in database
                with get_db_context() as db:
                    config = db.query(RobotConfig).filter_by(user_id=user_id).first()
                    if not config or not config.enabled:
                        logger.info("🛑 Robot disabled in database, stopping scan loop...")
                        self.running = False
                        break
                
                # Check again self.running (might have been set to False by stop())
                if not self.running:
                    logger.info("🛑 Robot stopped, exiting scan loop...")
                    break
                
                try:
                    await self._scan_and_trade(user_id)
                except Exception as e:
                    logger.error(f"Error in scan loop: {e}", exc_info=True)
                
                # Check again after scan (robot might have been stopped during scan)
                if not self.running:
                    logger.info("🛑 Robot stopped during scan, exiting loop...")
                    break
                
                # Get scan interval from config
                with get_db_context() as db:
                    config = db.query(RobotConfig).filter_by(user_id=user_id).first()
                    if not config or not config.enabled:
                        logger.info("🛑 Robot disabled, stopping scan loop...")
                        self.running = False
                        break
                    
                    scan_interval = config.scan_interval_seconds
                
                # Wait before next scan (but check for cancellation periodically)
                try:
                    await asyncio.sleep(scan_interval)
                except asyncio.CancelledError:
                    logger.info("Scan loop sleep cancelled")
                    break
        
        except asyncio.CancelledError:
            logger.info("✅ Scan loop cancelled successfully")
        except Exception as e:
            logger.error(f"Fatal error in scan loop: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("🛑 Scan loop stopped")
    
    async def manual_scan(self, user_id: int):
        """
        Manual scan - allows scanning even if robot is disabled (for testing/debugging)
        """
        logger.info(f"🔍 Manual scan triggered for user {user_id}...")
        
        with get_db_context() as db:
            config = db.query(RobotConfig).filter_by(user_id=user_id).first()
            if not config:
                logger.error(f"❌ Robot config not found for user {user_id}")
                raise ValueError(f"Robot config not found for user {user_id}")
            
            # Temporarily enable if disabled (only for this scan)
            original_enabled = config.enabled
            if not config.enabled:
                logger.info(f"⚠️ Robot is disabled, temporarily enabling for manual scan...")
                config.enabled = True
                db.commit()
                db.refresh(config)
            
            try:
                await self._scan_and_trade_internal(user_id, db, config)
            finally:
                # Restore original enabled state
                if not original_enabled:
                    config.enabled = False
                    db.commit()
    
    async def _scan_and_trade(self, user_id: int):
        """Scan market, get AI recommendations, execute trades (only if enabled)"""
        logger.info(f"🔍 Robot scanning market for user {user_id}...")
        
        with get_db_context() as db:
            # Get robot config
            config = db.query(RobotConfig).filter_by(user_id=user_id).first()
            if not config or not config.enabled:
                logger.debug(f"Robot disabled or config not found for user {user_id}")
                return
            
            await self._scan_and_trade_internal(user_id, db, config)
    
    async def _scan_and_trade_internal(self, user_id: int, db: Session, config: RobotConfig):
        """Internal scan logic (assumes config is enabled and validated)"""
        logger.info(f"✅ Robot config: Mode={config.trading_mode.value}, Confidence>={config.min_confidence}%, Positions={config.max_positions}, Capital=${config.capital_per_trade}")
        
        # Check cooldown (don't trade too frequently)
        if config.last_trade_at:
            # Both datetimes must be timezone-aware for comparison
            now_utc = datetime.now(timezone.utc)
            elapsed = (now_utc - config.last_trade_at).total_seconds()
            if elapsed < config.trade_cooldown_seconds:
                logger.info(f"⏸️ Trade cooldown active: {config.trade_cooldown_seconds - elapsed:.1f}s remaining")
                return
        
        # Safety check: max positions
        open_trades = db.query(Trade).filter_by(
            user_id=user_id,
            status=TradeStatus.OPEN
        ).all()
        
        open_trades_count = len(open_trades)
        if open_trades_count >= config.max_positions:
            logger.info(f"⏸️ Max positions reached: {open_trades_count}/{config.max_positions} - waiting for positions to close")
            return
        
        # Get list of symbols that already have open positions (avoid duplicate positions)
        open_symbols = {t.symbol for t in open_trades}
        logger.info(f"📊 Current open positions: {open_trades_count} - Symbols: {', '.join(open_symbols) if open_symbols else 'None'}")
        
        # Safety check: max daily loss
        # today_start must be timezone-aware to compare with Trade.created_at (which is timezone-aware)
        now_utc = datetime.now(timezone.utc)
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.created_at >= today_start,
            Trade.status == TradeStatus.CLOSED
        ).all()
        
        daily_pnl = sum(t.profit_loss or 0 for t in today_trades)
        if daily_pnl < -config.max_daily_loss:
            logger.warning(f"⚠️ Max daily loss reached: ${daily_pnl:.2f} / ${-config.max_daily_loss:.2f} - Robot paused")
            return
        
        # Get AI recommendations
        logger.info(f"🤖 Fetching AI recommendations (mode: {config.trading_mode.value})...")
        recommendations = await self._get_ai_recommendations(config, db)
        
        if not recommendations:
            logger.warning("⚠️ No AI recommendations returned - check AI service")
            return
        
        logger.info(f"📊 Received {len(recommendations)} AI recommendations")
        
        # Filter by confidence threshold - LOG ALL for debugging
        logger.info(f"🔍 Filtering by confidence >= {config.min_confidence}%...")
        logger.info(f"📋 All AI recommendations received:")
        for rec in recommendations:
            signal = rec.get('signal', 'UNKNOWN')
            confidence = rec.get('confidence', 0)
            symbol = rec.get('symbol', 'UNKNOWN')
            logger.info(f"   • {symbol}: {signal} ({confidence}%) - Entry: {rec.get('entry_price', 'N/A')}")
        
        filtered = [r for r in recommendations if r.get('confidence', 0) >= config.min_confidence]
        
        if not filtered:
            logger.warning(f"❌ No recommendations above confidence threshold ({config.min_confidence}%)!")
            logger.warning(f"   Highest confidence received: {max([r.get('confidence', 0) for r in recommendations], default=0)}%")
            logger.info(f"💡 Suggestion: Lower min_confidence from {config.min_confidence}% to 65% or check AI recommendations quality")
            return
        
        logger.info(f"✅ {len(filtered)} recommendations passed confidence filter")
        
        # Filter out HOLD signals (only execute BUY/SELL)
        actionable = []
        for r in filtered:
            signal = r.get('signal', '').upper().strip()
            symbol = r.get('symbol', '').strip()
            
            # STRICT filtering: Only accept BUY/SELL signals (reject HOLD, WAIT, etc.)
            if signal not in ['BUY', 'STRONG BUY', 'SELL', 'STRONG SELL']:
                logger.debug(f"   ⏭️ Skipping {symbol}: {signal} (not BUY/SELL)")
                continue
            
            # Skip if we already have an open position for this symbol
            # Normalize symbol for comparison (handle both BTC/USDT and BTCUSDT formats)
            symbol_normalized = symbol.replace('/USDT', '').replace('/USD', '').upper() + 'USDT'
            if symbol_normalized in open_symbols:
                logger.info(f"   ⏭️ Skipping {symbol}: Already have open position")
                continue
            
            actionable.append(r)
            logger.info(f"   ✅ {symbol}: {signal} ({r.get('confidence', 0)}%) - Actionable")
        
        if not actionable:
            logger.warning(f"❌ No actionable signals (BUY/SELL) after filtering!")
            logger.warning(f"   Reasons: All HOLD, or all symbols already have open positions")
            signals_list = [f"{r.get('symbol')}: {r.get('signal', 'UNKNOWN')}" for r in filtered]
            logger.info(f"   Signals received: {signals_list}")
            return
        
        logger.info(f"✅ {len(actionable)} actionable signals found (excluding HOLD and duplicates)")
        
        if len(actionable) == 0:
            logger.warning("⚠️ No actionable signals available after all filtering")
            return
        
        # Take best recommendation (highest confidence)
        best = sorted(actionable, key=lambda x: x.get('confidence', 0), reverse=True)[0]
        
        # Final check: Make sure we don't already have this symbol
        best_symbol_normalized = best.get('symbol', '').replace('/USDT', '').replace('/USD', '').upper() + 'USDT'
        if best_symbol_normalized in open_symbols:
            logger.warning(f"⚠️ Best recommendation {best.get('symbol')} already has open position - skipping")
            return
        
        logger.info(f"🎯 SELECTED: {best['symbol']} {best['signal']} ({best['confidence']}%)")
        logger.info(f"   Entry: {best.get('entry_price', 'N/A')}, Target: {best.get('target_price', 'N/A')}, Stop: {best.get('stop_loss', 'N/A')}")
        logger.info(f"   ✅ No duplicate position - proceeding with trade")
        
        # Execute trade
        await self._execute_trade(config, best, db)
    
    async def _get_ai_recommendations(self, config: RobotConfig, db: Session) -> List[Dict[str, Any]]:
        """Get AI recommendations from AI service"""
        try:
            # Import here to avoid circular dependency
            from app.services.ai_service import AIRecommendationService
            from app.services.market_sync_service import MarketSyncService
            from app.models import MarketSymbol
            
            ai_service = AIRecommendationService()
            
            # Get pinned symbols (or top 5 by volume)
            from app.models import User
            user = db.query(User).filter_by(id=config.user_id).first()
            if not user or not user.user_settings:
                # Fallback to top 5
                symbol_objs = db.query(MarketSymbol).filter(
                    MarketSymbol.asset_class == config.asset_class,
                    MarketSymbol.is_active == True
                ).order_by(MarketSymbol.volume_24h.desc()).limit(5).all()
            else:
                # Get pinned symbols
                if config.asset_class == AssetClass.CRYPTO:
                    pinned_str = user.user_settings.pinned_crypto_symbols
                else:
                    pinned_str = ""
                
                pinned_list = [s.strip() for s in pinned_str.split(',') if s.strip()]
                pinned_symbols = [s.replace('/USDT', '').replace('/USD', '').upper() + 'USDT' for s in pinned_list]
                
                symbol_objs = db.query(MarketSymbol).filter(
                    MarketSymbol.asset_class == config.asset_class,
                    MarketSymbol.is_active == True,
                    MarketSymbol.symbol.in_(pinned_symbols)
                ).all()
            
            if not symbol_objs:
                return []
            
            # Fetch market data
            market_data = []
            for symbol_obj in symbol_objs:
                try:
                    if self.binance_service:
                        ticker = await self.binance_service.get_24h_ticker(symbol_obj.symbol)
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
            
            if not market_data:
                return []
            
            # Get AI models from config
            ai_models = config.ai_models.split(',') if config.ai_models else ['deepseek']
            
            # Generate recommendations from first AI model
            # Mode determines timeframe: scalper=1-5min, normal=30min-4H, aggressive=15min-1H, longhold=Daily
            recommendations = await ai_service.generate_recommendations(
                mode=config.trading_mode.value,  # Use robot's configured mode
                market_data=market_data,
                asset_class=config.asset_class.value,
                technical_data=None,
                limit=5,
                history_context=None,
                ai_model=ai_models[0]
            )
            
            return recommendations
        
        except Exception as e:
            logger.error(f"Failed to get AI recommendations: {e}", exc_info=True)
            return []
    
    async def _execute_trade(self, config: RobotConfig, recommendation: Dict[str, Any], db: Session):
        """Execute trade based on AI recommendation"""
        try:
            symbol_raw = recommendation['symbol'].replace('/USD', '').replace('/USDT', '').replace('USDT', '').upper()
            symbol = f"{symbol_raw}USDT"
            signal = recommendation['signal'].upper()
            
            # Handle STRONG BUY/SELL as regular BUY/SELL
            if 'STRONG BUY' in signal or 'STRONG_BUY' in signal:
                signal = 'BUY'
            elif 'STRONG SELL' in signal or 'STRONG_SELL' in signal:
                signal = 'SELL'
            
            if signal not in ['BUY', 'SELL']:
                logger.warning(f"❌ Invalid signal: {signal} (expected BUY/SELL)")
                return
            
            logger.info(f"🚀 Executing trade: {signal} {symbol} (Confidence: {recommendation.get('confidence', 0)}%)")
            
            # Parse entry price - handle multiple formats
            entry_price_str = recommendation.get('entry_price', '0')
            entry_price = 0
            
            logger.info(f"📝 Parsing entry price: {entry_price_str} (type: {type(entry_price_str).__name__})")
            
            if isinstance(entry_price_str, str):
                # Remove common prefixes/suffixes
                entry_price_str = entry_price_str.replace('E:', '').replace('Entry:', '').replace('entry:', '').strip()
                # Remove $ and commas
                entry_price_str = entry_price_str.replace('$', '').replace(',', '').strip()
                # Try to extract number (handle ranges like "$95,000 - $95,500")
                if '-' in entry_price_str:
                    entry_price_str = entry_price_str.split('-')[0].strip()
                # Remove any non-numeric characters except decimal point
                entry_price_str = re.sub(r'[^\d.]', '', entry_price_str)
                
                try:
                    entry_price = float(entry_price_str) if entry_price_str else 0
                    logger.info(f"✅ Parsed entry price: ${entry_price:,.2f}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Failed to parse entry_price '{recommendation.get('entry_price')}': {e}")
                    entry_price = 0
            elif isinstance(entry_price_str, (int, float)):
                entry_price = float(entry_price_str)
                logger.info(f"✅ Entry price as number: ${entry_price:,.2f}")
            
            # If still no entry price, get current market price (ALWAYS try this as fallback)
            if entry_price == 0:
                logger.warning(f"⚠️ Entry price parsing failed or is 0, fetching current market price for {symbol}...")
                
            if entry_price == 0 and self.binance_service:
                try:
                    ticker = await self.binance_service.get_24h_ticker(symbol)
                    entry_price = float(ticker.get('lastPrice', 0))
                    logger.info(f"✅ Fetched current market price for {symbol}: ${entry_price:,.2f}")
                except Exception as e:
                    logger.error(f"❌ Failed to fetch market price for {symbol}: {e}")
                    return
            
            if entry_price == 0:
                logger.error(f"❌ CRITICAL: Cannot determine entry price for {symbol} - aborting trade")
                logger.error(f"   Entry price from AI: {recommendation.get('entry_price')}")
                logger.error(f"   Recommendation data: {recommendation}")
                return
            
            logger.info(f"💰 Final entry price: ${entry_price:,.2f}")
            
            # Parse Stop Loss (SL) from recommendation
            stop_loss = None
            stop_loss_str = recommendation.get('stop_loss', '')
            if stop_loss_str:
                logger.info(f"📝 Parsing stop loss: {stop_loss_str}")
                if isinstance(stop_loss_str, str):
                    # Remove common prefixes/suffixes
                    stop_loss_str = stop_loss_str.replace('SL:', '').replace('Stop:', '').replace('Stop Loss:', '').strip()
                    stop_loss_str = stop_loss_str.replace('$', '').replace(',', '').strip()
                    # Handle ranges
                    if '-' in stop_loss_str:
                        stop_loss_str = stop_loss_str.split('-')[0].strip()
                    # Remove non-numeric except decimal
                    stop_loss_str = re.sub(r'[^\d.]', '', stop_loss_str)
                    try:
                        stop_loss = float(stop_loss_str) if stop_loss_str else None
                        logger.info(f"✅ Parsed stop loss: ${stop_loss:,.2f}")
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Failed to parse stop_loss '{recommendation.get('stop_loss')}'")
                elif isinstance(stop_loss_str, (int, float)):
                    stop_loss = float(stop_loss_str)
                    logger.info(f"✅ Stop loss as number: ${stop_loss:,.2f}")
            
            # Parse Take Profit (TP/Target) from recommendation
            take_profit = None
            target_price_str = recommendation.get('target_price', '') or recommendation.get('take_profit', '')
            if target_price_str:
                logger.info(f"📝 Parsing take profit: {target_price_str}")
                if isinstance(target_price_str, str):
                    # Remove common prefixes/suffixes
                    target_price_str = target_price_str.replace('TP:', '').replace('Target:', '').replace('Take Profit:', '').strip()
                    target_price_str = target_price_str.replace('$', '').replace(',', '').strip()
                    # Handle ranges
                    if '-' in target_price_str:
                        target_price_str = target_price_str.split('-')[0].strip()
                    # Remove non-numeric except decimal
                    target_price_str = re.sub(r'[^\d.]', '', target_price_str)
                    try:
                        take_profit = float(target_price_str) if target_price_str else None
                        logger.info(f"✅ Parsed take profit: ${take_profit:,.2f}")
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Failed to parse target_price '{recommendation.get('target_price')}'")
                elif isinstance(target_price_str, (int, float)):
                    take_profit = float(target_price_str)
                    logger.info(f"✅ Take profit as number: ${take_profit:,.2f}")
            
            # Validate SL/TP logic
            if stop_loss and entry_price:
                if signal == 'BUY':
                    # For BUY: SL should be below entry, TP above entry
                    if stop_loss >= entry_price:
                        logger.warning(f"⚠️ Invalid SL for BUY: ${stop_loss:.2f} >= ${entry_price:.2f} - ignoring SL")
                        stop_loss = None
                else:  # SELL
                    # For SELL: SL should be above entry, TP below entry
                    if stop_loss <= entry_price:
                        logger.warning(f"⚠️ Invalid SL for SELL: ${stop_loss:.2f} <= ${entry_price:.2f} - ignoring SL")
                        stop_loss = None
            
            if take_profit and entry_price:
                if signal == 'BUY':
                    # For BUY: TP should be above entry
                    if take_profit <= entry_price:
                        logger.warning(f"⚠️ Invalid TP for BUY: ${take_profit:.2f} <= ${entry_price:.2f} - ignoring TP")
                        take_profit = None
                else:  # SELL
                    # For SELL: TP should be below entry
                    if take_profit >= entry_price:
                        logger.warning(f"⚠️ Invalid TP for SELL: ${take_profit:.2f} >= ${entry_price:.2f} - ignoring TP")
                        take_profit = None
            
            # Calculate quantity based on capital_per_trade
            # With leverage: quantity = (capital * leverage) / entry_price
            capital = config.capital_per_trade
            leverage = config.leverage
            quantity = (capital * leverage) / entry_price
            
            logger.info(f"💵 Trade params: Capital=${capital}, Leverage={leverage}x, Quantity={quantity:.6f}, Total=${capital * leverage:.2f}")
            if stop_loss:
                logger.info(f"🛑 Stop Loss: ${stop_loss:,.2f}")
            if take_profit:
                logger.info(f"🎯 Take Profit: ${take_profit:,.2f}")
            
            # Validate quantity
            if quantity <= 0:
                logger.error(f"❌ Invalid quantity calculated: {quantity} - aborting trade")
                return
            
            if quantity < 0.00001:  # Minimum trade size for most exchanges
                logger.warning(f"⚠️ Quantity too small: {quantity:.8f} - may be rejected by exchange")
            
            # Create trade record with SL/TP
            trade = Trade(
                user_id=config.user_id,
                symbol=symbol,
                side=TradeSide.BUY if signal == 'BUY' else TradeSide.SELL,
                quantity=quantity,
                entry_price=entry_price,
                leverage=leverage,
                status=TradeStatus.OPEN,
                trading_mode=config.trading_mode,
                ai_confidence=recommendation.get('confidence', 0),
                ai_reason=recommendation.get('reason', '')[:500] if recommendation.get('reason') else None,
                ai_model=recommendation.get('ai_model', 'unknown'),
                stop_loss=stop_loss,
                take_profit=take_profit,
                total_value=capital * leverage
            )
            
            db.add(trade)
            
            # Update robot config
            config.total_trades_executed += 1
            config.last_trade_at = datetime.now(timezone.utc)
            
            db.commit()
            
            sl_info = f", SL=${stop_loss:,.2f}" if stop_loss else ""
            tp_info = f", TP=${take_profit:,.2f}" if take_profit else ""
            logger.info(f"✅ Trade executed: {signal} {quantity:.6f} {symbol} @ ${entry_price:.2f} (Leverage: {leverage}x, Confidence: {recommendation.get('confidence', 0)}%{sl_info}{tp_info})")
        
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}", exc_info=True)
            db.rollback()


# Global robot instance
robot_service = RobotTradingService()

