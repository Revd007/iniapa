"""
Demo Account Service
Handles paper trading simulation without OAuth
User can test strategies with demo balance before going live
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import User, Trade, TradeMode, TradeStatus, APICredential

logger = logging.getLogger(__name__)


class DemoAccountService:
    """
    Service untuk simulasi trading tanpa OAuth
    Balance diambil dari database, tidak hardcode
    """
    
    @staticmethod
    def get_initial_balance(db: Session, user_id: int = 1) -> float:
        """
        Get initial demo balance dari database (api_credentials atau user settings)
        Jika belum ada, return default 1000.0 dan simpan ke database
        """
        # Check di api_credentials untuk demo balance
        cred = db.query(APICredential).filter_by(user_id=user_id).first()
        if cred and cred.account_balance is not None and cred.broker_name == 'demo':
            return cred.account_balance
        
        # Default untuk new user
        default_balance = 1000.0
        
        # Save default balance ke database
        if not cred:
            cred = APICredential(
                user_id=user_id,
                broker_name='demo',
                account_balance=default_balance,
                account_currency='USDT'
            )
            db.add(cred)
        else:
            cred.broker_name = 'demo'
            cred.account_balance = default_balance
            cred.account_currency = 'USDT'
        
        db.commit()
        return default_balance
    
    @staticmethod
    def get_demo_balance(db: Session, user_id: int = 1) -> Dict:
        """
        Calculate demo account balance dari trades
        Balance = initial balance (dari DB) + realized P&L + unrealized P&L
        """
        # Get initial balance dari database (bukan hardcode)
        initial_balance = DemoAccountService.get_initial_balance(db, user_id)
        
        # Get all demo trades for user
        all_trades = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.execution_mode == TradeMode.DEMO
        ).all()
        
        if not all_trades:
            return {
                'balance': initial_balance,
                'equity': initial_balance,
                'margin_used': 0.0,
                'free_margin': initial_balance,
                'total_trades': 0,
                'open_positions': 0
            }
        
        # Calculate realized P&L from closed trades
        closed_trades = [t for t in all_trades if t.status == TradeStatus.CLOSED]
        realized_pnl = sum(t.profit_loss or 0 for t in closed_trades)
        
        # Calculate unrealized P&L from open trades (simplified, use entry price)
        open_trades = [t for t in all_trades if t.status == TradeStatus.OPEN]
        unrealized_pnl = 0.0
        margin_used = 0.0
        
        for trade in open_trades:
            # Margin used
            margin_used += trade.total_value / (trade.leverage or 1)
            
            # Unrealized P&L (untuk demo, anggap price sama dengan entry)
            # Nanti akan di-update real-time di frontend
        
        balance = initial_balance + realized_pnl
        equity = balance + unrealized_pnl
        free_margin = equity - margin_used
        
        return {
            'balance': round(balance, 2),
            'equity': round(equity, 2),
            'margin_used': round(margin_used, 2),
            'free_margin': round(free_margin, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_trades': len(all_trades),
            'open_positions': len(open_trades),
            'mode': 'demo'
        }
    
    @staticmethod
    def can_open_trade(
        db: Session, 
        user_id: int,
        quantity: float,
        price: float,
        leverage: float = 1.0
    ) -> tuple[bool, str]:
        """
        Check if user can open trade (enough free margin)
        Returns: (can_trade, reason)
        """
        balance_info = DemoAccountService.get_demo_balance(db, user_id)
        
        required_margin = (quantity * price) / leverage
        free_margin = balance_info['free_margin']
        
        if required_margin > free_margin:
            return False, f"Insufficient margin. Required: ${required_margin:.2f}, Available: ${free_margin:.2f}"
        
        return True, "OK"
    
    @staticmethod
    def reset_demo_account(db: Session, user_id: int = 1):
        """
        Reset demo account - hapus semua demo trades
        Berguna untuk start fresh simulation
        """
        deleted = db.query(Trade).filter(
            Trade.user_id == user_id,
            Trade.execution_mode == TradeMode.DEMO
        ).delete()
        
        db.commit()
        logger.info(f"Reset demo account for user {user_id}: {deleted} trades deleted")
        return deleted


class LiveAccountService:
    """
    Service untuk live trading dengan OAuth
    Akan digunakan setelah OAuth verified
    """
    
    @staticmethod
    async def get_live_balance(
        db: Session,
        user_id: int,
        binance_access_token: str
    ) -> Dict:
        """
        Fetch real account balance dari Binance via OAuth
        TODO: Implement after OAuth verified
        """
        # TODO: Call Binance API with OAuth token
        # For now, return placeholder
        return {
            'balance': 0.0,
            'equity': 0.0,
            'margin_used': 0.0,
            'free_margin': 0.0,
            'mode': 'live',
            'status': 'oauth_not_configured'
        }

