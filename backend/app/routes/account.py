"""
Account routes
Provides summary for header (balance, environment, pnl, margin)
"""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, Trade
from app.config import settings

router = APIRouter()


@router.get("/summary")
async def get_account_summary(
    env: str = Query("auto", description="demo | live | auto"),
    asset_class: str = Query("crypto", description="crypto | forex"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Return account summary used by the header.
    This is inspired by Binance demo futures wallet view, but computed locally
    from trades and configurable starting balances.
    """
    try:
        # Decide environment
        if env not in ("auto", "demo", "live"):
            raise HTTPException(status_code=400, detail="env must be auto | demo | live")

        if env == "auto":
            environment = "demo" if settings.BINANCE_TESTNET else "live"
        else:
            environment = env

        # External account summary preference
        base_balance = 0.0
        equity = 0.0
        margin_used = 0.0

        # Try to get real balances from Binance (crypto) or MT5 (forex)
        if asset_class == "forex":
            mt5_service = getattr(request.app.state, "mt5_service", None) if request else None
            if mt5_service and settings.MT5_ENABLED:
                mt5_summary = await mt5_service.get_account_summary()
                if mt5_summary:
                    base_balance = mt5_summary["balance"]
                    equity = mt5_summary["equity"]
                    margin_used = mt5_summary["margin"]
        else:
            # Crypto: prefer Binance account info if available
            binance_service = getattr(request.app.state, "binance_service", None) if request else None
            if binance_service:
                try:
                    account_info = await binance_service.get_account_info()
                    balances = account_info.get("balances", [])
                    usdt = next((b for b in balances if b.get("asset") == "USDT"), None)
                    if usdt:
                        free = float(usdt.get("free", 0))
                        locked = float(usdt.get("locked", 0))
                        base_balance = free + locked
                        equity = base_balance
                except Exception:
                    # Fallback handled below
                    pass

        # If external equity not available, fall back to configured demo/live start
        if equity == 0.0:
            demo_start = float(os.getenv("DEMO_START_BALANCE", "10000"))
            live_start = float(os.getenv("LIVE_START_BALANCE", "0"))
            base_balance = demo_start if environment == "demo" else live_start
            equity = base_balance

        # Aggregate trades (currently not split per env; could be extended later)
        all_trades = db.query(Trade).all()
        closed_trades = [t for t in all_trades if t.status == "CLOSED"]
        open_trades = [t for t in all_trades if t.status == "OPEN"]

        realized_pnl = sum(t.profit_loss or 0 for t in closed_trades)

        # Unrealized from open trades using entry price as mark price placeholder
        unrealized_pnl = 0.0
        margin_used = 0.0
        for t in open_trades:
            current_price = t.price
            if t.side == "BUY":
                pnl = (current_price - t.entry_price) * t.quantity * (t.leverage or 1)
            else:
                pnl = (t.entry_price - current_price) * t.quantity * (t.leverage or 1)
            unrealized_pnl += pnl

            margin = t.total_value / (t.leverage or 1)
            margin_used += margin

        equity = equity + realized_pnl + unrealized_pnl
        available_balance = equity - margin_used

        # Trades today
        today = datetime.utcnow().date()
        trades_today = (
            db.query(Trade).filter(func.date(Trade.created_at) == today).count()
        )

        return {
            "success": True,
            "environment": environment,
            "base_balance": base_balance,
            "equity": round(equity, 2),
            "available_balance": round(available_balance, 2),
            "margin_used": round(margin_used, 2),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "trades_today": trades_today,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


