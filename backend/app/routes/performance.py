"""
Performance Dashboard Routes
Endpoints for tracking trading performance metrics
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging
from typing import Optional

from app.database import get_db, Trade

logger = logging.getLogger(__name__)

router = APIRouter()


def get_binance_service(request: Request):
    """Dependency to get binance service from app state"""
    try:
        return request.app.state.binance_service
    except AttributeError:
        return None


@router.get("/dashboard")
async def get_performance_dashboard(
    asset_class: str = "crypto",
    env: str = "demo",  # demo or live
    request: Optional[Request] = Depends(lambda: None),  # Optional dependency
    db: Session = Depends(get_db)
):
    """Get real-time performance dashboard metrics with live mark prices"""
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
        
        # All trades filtered by environment
        all_trades = db.query(Trade).filter(Trade.execution_mode == execution_mode).all()
        closed_trades = [t for t in all_trades if t.status == "CLOSED"]
        open_trades = [t for t in all_trades if t.status == "OPEN"]

        # If no trades at all, return zeros
        if not all_trades:
            return {
                "success": True,
                "metrics": {
                    "total_profit": 0,
                    "profit_percent": 0,
                    "win_rate": 0,
                    "risk_reward_ratio": "0:0",
                    "trades_today": 0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "unrealized_pnl": 0,
                    "realized_pnl": 0,
                },
                "daily_profit": [],
                "win_rate_distribution": [
                    {"name": "Wins", "value": 0},
                    {"name": "Losses", "value": 0},
                ],
            }

        # Realized PnL from closed trades
        realized_pnl = sum(t.profit_loss or 0 for t in closed_trades)

        # Unrealized PnL from open trades (use DB data - mark_price stored in positions endpoint)
        # For performance, we calculate based on entry_price (or fetch mark prices in batch if needed)
        unrealized_pnl = 0.0
        
        # Calculate unrealized PnL from open trades
        # For performance, we use entry_price as fallback (mark prices are fetched in positions endpoint)
        # If we need real-time prices, we can fetch them here, but for now use entry_price
        for t in open_trades:
            # Use entry_price for unrealized PnL calculation (mark prices are already in positions endpoint)
            current_price = t.entry_price
            if t.side == "BUY":
                diff = (current_price - t.entry_price) * t.quantity * (t.leverage or 1)
            else:
                diff = (t.entry_price - current_price) * t.quantity * (t.leverage or 1)
            unrealized_pnl += diff

        total_profit = realized_pnl + unrealized_pnl

        winning_trades = [t for t in closed_trades if t.is_win]
        losing_trades = [t for t in closed_trades if t.is_win is False]

        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0

        # Calculate risk/reward ratio from closed trades
        avg_win = sum(t.profit_loss or 0 for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t.profit_loss or 0 for t in losing_trades) / len(losing_trades)) if losing_trades else 1
        risk_reward = f"1:{avg_win/avg_loss:.1f}" if avg_loss > 0 else "1:0"

        # Trades today (open + closed created today) - filtered by environment
        today = datetime.utcnow().date()
        trades_today = db.query(Trade).filter(
            Trade.execution_mode == execution_mode,
            func.date(Trade.created_at) == today
        ).count()
        
        # Daily profit for last 7 days - filtered by environment
        daily_profit = []
        for i in range(6, -1, -1):
            day = datetime.utcnow().date() - timedelta(days=i)
            # Filter closed trades by both date and execution_mode
            day_trades = [
                t for t in closed_trades 
                if t.closed_at and t.closed_at.date() == day and t.execution_mode == execution_mode
            ]
            day_profit = sum(t.profit_loss for t in day_trades if t.profit_loss) if day_trades else 0
            daily_profit.append({
                "day": day.strftime("%a"),
                "profit": round(day_profit, 2)
            })
        
        return {
            "success": True,
                "metrics": {
                    "total_profit": round(total_profit, 2),
                    "realized_pnl": round(realized_pnl, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "profit_percent": round(
                        (total_profit / sum(t.total_value for t in all_trades) * 100)
                        if all_trades
                        else 0,
                        2,
                    ),
                    "win_rate": round(win_rate, 1),
                    "risk_reward_ratio": risk_reward,
                    "trades_today": trades_today,
                    "total_trades": len(all_trades),
                    "winning_trades": len(winning_trades),
                    "losing_trades": len(losing_trades),
                },
            "daily_profit": daily_profit,
            "win_rate_distribution": [
                {"name": "Wins", "value": len(winning_trades)},
                {"name": "Losses", "value": len(losing_trades)}
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_performance_stats(db: Session = Depends(get_db)):
    """Get detailed performance statistics"""
    try:
        # All trades
        all_trades = db.query(Trade).all()
        closed_trades = [t for t in all_trades if t.status == "CLOSED"]
        open_trades = [t for t in all_trades if t.status == "OPEN"]
        
        # Calculate comprehensive stats
        total_volume = sum(t.total_value for t in all_trades)
        total_profit = sum(t.profit_loss for t in closed_trades if t.profit_loss)
        
        # Best and worst trades
        best_trade = max(closed_trades, key=lambda t: t.profit_loss or 0) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.profit_loss or 0) if closed_trades else None
        
        # Mode breakdown
        mode_stats = {}
        for mode in ["scalper", "normal", "aggressive", "longhold"]:
            mode_trades = [t for t in closed_trades if t.trading_mode == mode]
            if mode_trades:
                mode_profit = sum(t.profit_loss for t in mode_trades if t.profit_loss)
                mode_wins = len([t for t in mode_trades if t.is_win])
                mode_stats[mode] = {
                    "trades": len(mode_trades),
                    "profit": round(mode_profit, 2),
                    "win_rate": round(mode_wins / len(mode_trades) * 100, 1) if mode_trades else 0
                }
        
        return {
            "success": True,
            "stats": {
                "total_trades": len(all_trades),
                "open_trades": len(open_trades),
                "closed_trades": len(closed_trades),
                "total_volume": round(total_volume, 2),
                "total_profit": round(total_profit, 2),
                "best_trade": {
                    "symbol": best_trade.symbol,
                    "profit": round(best_trade.profit_loss, 2)
                } if best_trade else None,
                "worst_trade": {
                    "symbol": worst_trade.symbol,
                    "loss": round(worst_trade.profit_loss, 2)
                } if worst_trade else None,
                "mode_breakdown": mode_stats
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profit-chart")
async def get_profit_chart(
    days: int = 30,
    env: str = "demo",  # demo or live
    db: Session = Depends(get_db)
):
    """Get profit chart data for specified number of days"""
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
        
        chart_data = []
        cumulative_profit = 0
        
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow().date() - timedelta(days=i)
            
            # Get trades for this day - filtered by environment
            day_trades = db.query(Trade).filter(
                Trade.status == "CLOSED",
                Trade.execution_mode == execution_mode,
                func.date(Trade.closed_at) == day
            ).all()
            
            day_profit = sum(t.profit_loss for t in day_trades if t.profit_loss) if day_trades else 0
            cumulative_profit += day_profit
            
            chart_data.append({
                "date": day.strftime("%Y-%m-%d"),
                "daily_profit": round(day_profit, 2),
                "cumulative_profit": round(cumulative_profit, 2),
                "trades": len(day_trades)
            })
        
        return {
            "success": True,
            "chart_data": chart_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get profit chart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

