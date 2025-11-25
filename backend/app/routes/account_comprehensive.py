"""
Comprehensive Account Routes
Detailed account information, balance, and withdrawal functionality
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.database import get_db
from app.models import APICredential, WithdrawalHistory, WithdrawalStatus
from app.config import settings
from app.routes.settings import decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter()


class WithdrawRequest(BaseModel):
    asset: str
    amount: float
    address: str
    network: Optional[str] = None
    address_tag: Optional[str] = None
    name: Optional[str] = None


@router.get("/comprehensive")
async def get_comprehensive_account_info(
    request: Request,
    env: str = Query("demo", description="demo or live"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive account information including:
    - Portfolio Margin account info
    - Account balance (all assets)
    - Account equity, margin, etc.
    
    Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Account-Information
    """
    try:
        user_id = 1  # Default user for now
        
        # Get user's API credentials if exists
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        # Get binance service
        binance_service = request.app.state.binance_service
        
        # Temporarily override API keys and testnet mode if user has custom keys
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        original_testnet = binance_service.testnet
        
        try:
            if api_creds and api_creds.binance_api_key:
                api_key = decrypt_value(api_creds.binance_api_key)
                api_secret = decrypt_value(api_creds.binance_api_secret)
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
                # Prioritize env parameter from request (user's current selection) over stored environment
                # This allows user to switch between demo/live dynamically
                custom_env = env or api_creds.environment or 'demo'
            else:
                # Use default keys from settings
                if env == "demo":
                    api_key = settings.BINANCE_DEMO_API_KEY
                    api_secret = settings.BINANCE_DEMO_API_SECRET
                else:
                    api_key = settings.BINANCE_LIVE_API_KEY
                    api_secret = settings.BINANCE_LIVE_API_SECRET
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
                custom_env = env
            
            # Set testnet mode based on environment
            binance_service.testnet = (custom_env == 'demo')
            if binance_service.testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
            
            # Get Portfolio Margin account info
            portfolio_info = {}
            try:
                portfolio_info = await binance_service.get_portfolio_margin_account_info()
            except Exception as e:
                logger.warning(f"Portfolio Margin account info failed: {e}")
                # Fallback to spot account
                spot_account = await binance_service.get_account_info()
                portfolio_info = {
                    "accountEquity": sum(float(b.get('free', 0)) for b in spot_account.get('balances', [])),
                    "accountStatus": "NORMAL",
                    "canTrade": spot_account.get('canTrade', False),
                    "canWithdraw": spot_account.get('canWithdraw', False),
                    "canDeposit": spot_account.get('canDeposit', False),
                }
            
            # Get Portfolio Margin balance
            balance_data = []
            try:
                balance_data = await binance_service.get_portfolio_margin_balance()
                if not isinstance(balance_data, list):
                    balance_data = [balance_data] if balance_data else []
            except Exception as e:
                logger.warning(f"Portfolio Margin balance failed: {e}")
                # Fallback to spot balance
                spot_account = await binance_service.get_account_info()
                balance_data = spot_account.get('balances', [])
            
            # Format balance data
            formatted_balances = []
            for balance in balance_data:
                if isinstance(balance, dict):
                    asset = balance.get('asset', '')
                    if asset:
                        formatted_balances.append({
                            "asset": asset,
                            "totalWalletBalance": float(balance.get('totalWalletBalance', balance.get('free', 0))),
                            "available": float(balance.get('free', balance.get('crossMarginFree', 0))),
                            "locked": float(balance.get('locked', balance.get('crossMarginLocked', 0))),
                            "crossMarginAsset": float(balance.get('crossMarginAsset', 0)),
                            "crossMarginBorrowed": float(balance.get('crossMarginBorrowed', 0)),
                            "umWalletBalance": float(balance.get('umWalletBalance', 0)),
                            "umUnrealizedPNL": float(balance.get('umUnrealizedPNL', 0)),
                            "cmWalletBalance": float(balance.get('cmWalletBalance', 0)),
                            "cmUnrealizedPNL": float(balance.get('cmUnrealizedPNL', 0)),
                        })
            
            return {
                "success": True,
                "environment": custom_env,
                "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                "account_info": {
                    "accountEquity": float(portfolio_info.get('accountEquity', portfolio_info.get('accountEquity', 0))),
                    "accountInitialMargin": float(portfolio_info.get('accountInitialMargin', 0)),
                    "accountMaintMargin": float(portfolio_info.get('accountMaintMargin', 0)),
                    "accountStatus": portfolio_info.get('accountStatus', 'NORMAL'),
                    "canTrade": portfolio_info.get('canTrade', False),
                    "canWithdraw": portfolio_info.get('canWithdraw', False),
                    "canDeposit": portfolio_info.get('canDeposit', False),
                    "virtualMaxWithdrawAmount": float(portfolio_info.get('virtualMaxWithdrawAmount', 0)),
                    "updateTime": portfolio_info.get('updateTime', 0),
                },
                "balances": formatted_balances,
                "total_assets": len(formatted_balances),
            }
            
        finally:
            # Restore original keys and testnet mode
            binance_service.api_key = original_key
            binance_service.api_secret = original_secret
            binance_service.testnet = original_testnet
            if original_testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
        
    except Exception as e:
        logger.error(f"Failed to get comprehensive account info: {e}", exc_info=True)
        return {
            "success": False,
            "environment": env,
            "error": str(e),
            "account_info": {},
            "balances": []
        }


@router.get("/max-withdraw")
async def get_max_withdraw(
    request: Request,
    asset: str = Query(..., description="Asset symbol (e.g., USDT)"),
    env: str = Query("demo", description="demo or live"),
    db: Session = Depends(get_db)
):
    """
    Get maximum withdrawable amount for an asset
    Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-Margin-Max-Withdraw
    """
    try:
        user_id = 1
        
        # Get user's API credentials if exists
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        # Get binance service
        binance_service = request.app.state.binance_service
        
        # Temporarily override API keys and testnet mode if user has custom keys
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        original_testnet = binance_service.testnet
        
        try:
            if api_creds and api_creds.binance_api_key:
                api_key = decrypt_value(api_creds.binance_api_key)
                api_secret = decrypt_value(api_creds.binance_api_secret)
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
            else:
                if env == "demo":
                    api_key = settings.BINANCE_DEMO_API_KEY
                    api_secret = settings.BINANCE_DEMO_API_SECRET
                else:
                    api_key = settings.BINANCE_LIVE_API_KEY
                    api_secret = settings.BINANCE_LIVE_API_SECRET
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
            
            # Set testnet mode based on environment
            binance_service.testnet = (env == 'demo')
            if binance_service.testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
            
            # Get max withdraw
            max_withdraw = await binance_service.get_max_withdraw(asset)
            
            return {
                "success": True,
                "asset": asset,
                "max_withdraw_amount": float(max_withdraw.get('amount', 0)),
            }
            
        finally:
            # Restore original keys and testnet mode
            binance_service.api_key = original_key
            binance_service.api_secret = original_secret
            binance_service.testnet = original_testnet
            if original_testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
        
    except Exception as e:
        logger.error(f"Failed to get max withdraw: {e}")
        return {
            "success": False,
            "asset": asset,
            "max_withdraw_amount": 0,
            "error": str(e)
        }


@router.post("/withdraw")
async def withdraw_funds(
    request: Request,
    withdraw_data: WithdrawRequest,
    env: str = Query("demo", description="demo or live"),
    db: Session = Depends(get_db)
):
    """
    Withdraw funds from account
    Reference: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/withdraw
    
    ⚠️ WARNING: This is a real withdrawal that moves funds out of your account!
    """
    try:
        user_id = 1
        
        # Get user's API credentials if exists
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        # Get binance service
        binance_service = request.app.state.binance_service
        
        # Temporarily override API keys and testnet mode if user has custom keys
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        original_testnet = binance_service.testnet
        
        # Create withdrawal record in database
        withdrawal_record = WithdrawalHistory(
            user_id=user_id,
            asset=withdraw_data.asset,
            amount=withdraw_data.amount,
            address=withdraw_data.address,
            network=withdraw_data.network,
            address_tag=withdraw_data.address_tag,
            name=withdraw_data.name,
            environment=env,
            status=WithdrawalStatus.PENDING
        )
        db.add(withdrawal_record)
        db.flush()  # Get the ID
        
        try:
            if api_creds and api_creds.binance_api_key:
                api_key = decrypt_value(api_creds.binance_api_key)
                api_secret = decrypt_value(api_creds.binance_api_secret)
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
            else:
                if env == "demo":
                    api_key = settings.BINANCE_DEMO_API_KEY
                    api_secret = settings.BINANCE_DEMO_API_SECRET
                else:
                    api_key = settings.BINANCE_LIVE_API_KEY
                    api_secret = settings.BINANCE_LIVE_API_SECRET
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
            
            # Set testnet mode based on environment
            binance_service.testnet = (env == 'demo')
            if binance_service.testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
            
            # Validate amount
            if withdraw_data.amount <= 0:
                withdrawal_record.status = WithdrawalStatus.FAILED
                withdrawal_record.error_message = "Amount must be greater than 0"
                db.commit()
                raise HTTPException(status_code=400, detail="Amount must be greater than 0")
            
            # Check max withdraw
            max_withdraw = await binance_service.get_max_withdraw(withdraw_data.asset)
            max_amount = float(max_withdraw.get('amount', 0))
            
            if withdraw_data.amount > max_amount:
                withdrawal_record.status = WithdrawalStatus.FAILED
                withdrawal_record.error_message = f"Amount exceeds maximum withdrawable: {max_amount} {withdraw_data.asset}"
                db.commit()
                raise HTTPException(
                    status_code=400,
                    detail=f"Amount exceeds maximum withdrawable: {max_amount} {withdraw_data.asset}"
                )
            
            # Execute withdrawal
            result = await binance_service.withdraw(
                asset=withdraw_data.asset,
                amount=withdraw_data.amount,
                address=withdraw_data.address,
                network=withdraw_data.network,
                address_tag=withdraw_data.address_tag,
                name=withdraw_data.name
            )
            
            # Update withdrawal record with result
            withdrawal_record.withdrawal_id = result.get('id', '')
            withdrawal_record.status = WithdrawalStatus.PROCESSING
            withdrawal_record.tx_id = result.get('txId', '')
            db.commit()
            
            logger.info(f"Withdrawal initiated: {withdraw_data.amount} {withdraw_data.asset} to {withdraw_data.address}")
            
            return {
                "success": True,
                "message": "Withdrawal initiated successfully",
                "withdrawal_id": result.get('id', ''),
                "asset": withdraw_data.asset,
                "amount": withdraw_data.amount,
                "address": withdraw_data.address,
                "db_id": withdrawal_record.id
            }
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            # Update withdrawal record with error
            withdrawal_record.status = WithdrawalStatus.FAILED
            withdrawal_record.error_message = str(e)
            db.commit()
            logger.error(f"Failed to withdraw: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Restore original keys and testnet mode
            binance_service.api_key = original_key
            binance_service.api_secret = original_secret
            binance_service.testnet = original_testnet
            if original_testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to withdraw: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/withdrawal-history")
async def get_withdrawal_history(
    request: Request,
    env: str = Query("demo", description="demo or live"),
    limit: int = Query(50, description="Number of records to return"),
    db: Session = Depends(get_db)
):
    """Get withdrawal history for the user"""
    try:
        user_id = 1  # Default user for now
        
        withdrawals = db.query(WithdrawalHistory).filter_by(
            user_id=user_id,
            environment=env
        ).order_by(WithdrawalHistory.created_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "withdrawals": [
                {
                    "id": w.id,
                    "asset": w.asset,
                    "amount": w.amount,
                    "address": w.address,
                    "network": w.network,
                    "address_tag": w.address_tag,
                    "name": w.name,
                    "status": w.status.value,
                    "withdrawal_id": w.withdrawal_id,
                    "transaction_id": w.tx_id,
                    "error_message": w.error_message,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                    "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                }
                for w in withdrawals
            ],
            "total": len(withdrawals)
        }
    except Exception as e:
        logger.error(f"Failed to get withdrawal history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

