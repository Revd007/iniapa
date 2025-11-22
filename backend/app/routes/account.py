"""
Account Routes
Dual-mode account management: Demo (simulation) & Live (OAuth)
Clean separation untuk testing dan production trading
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, Trade
from app.models import TradeMode
from app.config import settings
from app.services.demo_account_service import DemoAccountService

router = APIRouter()


@router.get("/summary")
async def get_account_summary(
    mode: str = Query(None, description="demo | live (deprecated, use env)"),
    env: str = Query("demo", description="demo | live"),
    asset_class: str = Query("crypto", description="crypto | forex"),
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
):
    """
    Account summary dengan dual-mode:
    - demo: Paper trading, simulation dengan balance virtual
    - live: OAuth-authenticated, real account (coming soon)
    
    Semua trades di-track terpisah berdasarkan execution_mode
    
    Note: Frontend menggunakan 'env' parameter, backend support both 'mode' dan 'env'
    """
    try:
        # Support both 'mode' and 'env' for backward compatibility
        trading_mode = env if env else (mode if mode else "demo")
        
        if trading_mode not in ("demo", "live"):
            raise HTTPException(status_code=400, detail="mode/env must be demo or live")
        
        # Demo mode: simulasi trading dengan balance virtual
        if trading_mode == "demo":
            balance_info = DemoAccountService.get_demo_balance(db, user_id)
            
            # Get trades count for today
            today = datetime.utcnow().date()
            trades_today = db.query(Trade).filter(
                Trade.user_id == user_id,
                Trade.execution_mode == TradeMode.DEMO,
                func.date(Trade.created_at) == today
            ).count()
            
            return {
                "success": True,
                "mode": "demo",
                "environment": "simulation",
                "balance": balance_info['balance'],
                "equity": balance_info['equity'],
                "available_balance": balance_info['free_margin'],
                "margin_used": balance_info['margin_used'],
                "realized_pnl": balance_info['realized_pnl'],
                "unrealized_pnl": balance_info['unrealized_pnl'],
                "trades_today": trades_today,
                "total_trades": balance_info['total_trades'],
                "open_positions": balance_info['open_positions'],
                "broker": "demo",
                "currency": "USDT"
            }
        
        # Live mode: OAuth-authenticated real trading
        # TODO: Implement after OAuth verified
        elif trading_mode == "live":
            if not settings.OAUTH_ENABLED:
                return {
                    "success": False,
                    "mode": "live",
                    "message": "OAuth not enabled. Use demo mode for simulation.",
                    "balance": 0.0,
                    "equity": 0.0,
                    "available_balance": 0.0,
                    "margin_used": 0.0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "trades_today": 0
                }
            
            # TODO: Get balance from Binance/MT5 via OAuth token
            # For now, return placeholder
            return {
                "success": True,
                "mode": "live",
                "environment": "production",
                "message": "OAuth integration coming soon",
                "balance": 0.0,
                "equity": 0.0,
                "available_balance": 0.0,
                "margin_used": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "trades_today": 0,
                "broker": "binance",
                "currency": "USDT"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-demo")
async def reset_demo_account(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Reset demo account - hapus semua demo trades
    Berguna untuk start fresh simulation
    """
    try:
        deleted_count = DemoAccountService.reset_demo_account(db, user_id)
        
        # Get initial balance dari database (bukan hardcode)
        initial_balance = DemoAccountService.get_initial_balance(db, user_id)
        
        return {
            "success": True,
            "message": f"Demo account reset successfully. {deleted_count} trades deleted.",
            "deleted_trades": deleted_count,
            "new_balance": initial_balance
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


