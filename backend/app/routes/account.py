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
from app.models import TradeMode, TradeStatus
from app.config import settings
from app.services.demo_account_service import DemoAccountService
from cryptography.fernet import Fernet
import base64
import hashlib

router = APIRouter()

# Encryption helper (same as in settings.py)
ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"nof1trading_secret_key").digest())
cipher = Fernet(ENCRYPTION_KEY)

def decrypt_value(value: str) -> str:
    """Decrypt sensitive value"""
    try:
        return cipher.decrypt(value.encode()).decode()
    except:
        return ""


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
                "environment": "demo",  # Use 'demo' instead of 'simulation' for consistency
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
        
        # Live mode: Get real balance from Binance API
        elif trading_mode == "live":
            from app.models import APICredential
            from app.services.binance_service import BinanceService
            import logging
            
            logger = logging.getLogger(__name__)
            
            try:
                # Get user's API credentials
                api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
                
                if not api_creds or not api_creds.binance_api_key:
                    return {
                        "success": False,
                        "mode": "live",
                        "environment": "production",
                        "message": "API keys not configured. Please configure in Settings.",
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
                
                # Get binance service from app state (need to import Request)
                from fastapi import Request as FastAPIRequest
                # We need to get request from context, but since we don't have it here,
                # we'll create a new BinanceService instance
                binance_service = BinanceService()
                binance_service.api_key = decrypt_value(api_creds.binance_api_key)
                binance_service.api_secret = decrypt_value(api_creds.binance_api_secret)
                binance_service.testnet = False  # Live mode
                binance_service.base_url = "https://api.binance.com/api"
                
                try:
                    await binance_service.initialize()
                    
                    # Get account info - prioritize Futures account
                    account = None
                    futures_account = None
                    account_type = 'SPOT'
                    
                    try:
                        # Try Futures account first (preferred for Futures trading)
                        try:
                            logger.info("🔄 Attempting to fetch Futures account for live mode...")
                            futures_account = await binance_service.get_futures_account_info()
                            if futures_account:
                                account_type = 'FUTURES'
                                logger.info(f"✅ Futures account detected for live mode! Balance: {futures_account.get('totalWalletBalance', 0)}")
                            else:
                                logger.warning("Futures account response is empty, falling back to Spot")
                        except Exception as e:
                            logger.warning(f"⚠️ Futures account fetch failed: {e}")
                            logger.info("🔄 Falling back to Spot account...")
                        
                        # If Futures failed, try Spot account
                        if not futures_account:
                            try:
                                account = await binance_service.get_account()
                                logger.info(f"✅ Spot account info fetched successfully for live mode")
                                account_type = 'SPOT'
                            except Exception as e:
                                logger.error(f"❌ Both Futures and Spot account fetch failed: {e}")
                                raise
                        else:
                            # Futures succeeded, still try to get Spot for additional info
                            try:
                                account = await binance_service.get_account()
                            except:
                                account = None
                    except Exception as e:
                        logger.error(f"Failed to fetch account info: {e}")
                        return {
                            "success": False,
                            "mode": "live",
                            "environment": "production",
                            "message": f"Failed to fetch account info: {str(e)}",
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
                    
                    # Extract balance
                    balance = 0.0
                    equity = 0.0
                    available_balance = 0.0
                    margin_used = 0.0
                    unrealized_pnl = 0.0
                    
                    if account_type == 'FUTURES' and futures_account:
                        # Use Futures account balance
                        balance = float(futures_account.get('totalWalletBalance', 0))
                        equity = float(futures_account.get('totalWalletBalance', 0)) + float(futures_account.get('totalUnrealizedProfit', 0))
                        available_balance = float(futures_account.get('availableBalance', 0))
                        margin_used = float(futures_account.get('totalInitialMargin', 0))
                        unrealized_pnl = float(futures_account.get('totalUnrealizedProfit', 0))
                    elif account:
                        # Use Spot account balance
                        balances = account.get('balances', [])
                        usdt_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDT'), 0)
                        balance = usdt_balance
                        equity = usdt_balance
                        available_balance = usdt_balance
                        margin_used = 0.0
                        unrealized_pnl = 0.0
                    
                    # Get trades count for today
                    today = datetime.utcnow().date()
                    trades_today = db.query(Trade).filter(
                        Trade.user_id == user_id,
                        Trade.execution_mode == TradeMode.LIVE,
                        func.date(Trade.created_at) == today
                    ).count()
                    
                    total_trades = db.query(Trade).filter(
                        Trade.user_id == user_id,
                        Trade.execution_mode == TradeMode.LIVE
                    ).count()
                    
                    open_positions = db.query(Trade).filter(
                        Trade.user_id == user_id,
                        Trade.execution_mode == TradeMode.LIVE,
                        Trade.status == TradeStatus.OPEN
                    ).count()
                    
                    return {
                        "success": True,
                        "mode": "live",
                        "environment": "production",
                        "balance": balance,
                        "equity": equity,
                        "available_balance": available_balance,
                        "margin_used": margin_used,
                        "realized_pnl": 0.0,  # TODO: Calculate from closed trades
                        "unrealized_pnl": unrealized_pnl,
                        "trades_today": trades_today,
                        "total_trades": total_trades,
                        "open_positions": open_positions,
                        "broker": "binance",
                        "currency": "USDT",
                        "account_type": account_type
                    }
                finally:
                    # Always close the binance service session
                    try:
                        await binance_service.close()
                    except Exception as e:
                        logger.warning(f"Error closing binance service: {e}")
                
            except Exception as e:
                logger.error(f"Error fetching live account summary: {e}")
                return {
                    "success": False,
                    "mode": "live",
                    "environment": "production",
                    "message": f"Error: {str(e)}",
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


