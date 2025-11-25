"""
Settings API Routes
User settings for API keys, environment, and account configuration
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import base64
import hashlib
import logging

from app.database import get_db
from app.models import User, APICredential
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple encryption key (in production, use proper key management)
ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"nof1trading_secret_key").digest())
cipher = Fernet(ENCRYPTION_KEY)


class APIKeySettings(BaseModel):
    binance_api_key: str
    binance_api_secret: str
    environment: str  # 'demo' or 'live'


def encrypt_value(value: str) -> str:
    """Encrypt sensitive value"""
    return cipher.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt sensitive value"""
    try:
        return cipher.decrypt(value.encode()).decode()
    except:
        return ""


@router.get("/account-info")
async def get_account_info(
    request: Request,
    env: str = "demo",
    db: Session = Depends(get_db)
):
    """
    Get account information including balance
    This will use user's custom API keys if set, or default keys
    """
    try:
        user_id = 1  # Default user for now
        
        # Get user's API credentials if exists
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if api_creds and api_creds.binance_api_key:
            # Use user's custom API keys
            api_key = decrypt_value(api_creds.binance_api_key)
            api_secret = decrypt_value(api_creds.binance_api_secret)
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
            custom_env = env
        
        # Get binance service
        binance_service = request.app.state.binance_service
        
        # Temporarily override API keys and testnet mode if needed
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        original_testnet = binance_service.testnet
        
        try:
            # Set API keys and testnet mode based on environment
            binance_service.api_key = api_key
            binance_service.api_secret = api_secret
            # Set testnet mode: demo = True (testnet), live = False (production)
            binance_service.testnet = (custom_env == 'demo')
            
            # Update base URL based on testnet mode
            if binance_service.testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
            
            # Get account info from Binance
            # Try Spot account first
            account = None
            futures_account = None
            account_type = ''
            
            try:
                account = await binance_service.get_account()
                permissions = account.get('permissions', [])
                
                # Check if Futures permission is enabled
                has_futures_permission = 'FUTURES' in permissions or 'Enable Futures' in str(permissions)
                
                if has_futures_permission:
                    # Try to get Futures account
                    try:
                        futures_account = await binance_service.get_futures_account_info()
                        if futures_account:
                            account_type = 'FUTURES'
                            logger.info("Futures account detected, using Futures account info")
                    except Exception as e:
                        logger.warning(f"Futures account fetch failed, using Spot account: {e}")
            except Exception as e:
                logger.error(f"Failed to fetch account info: {e}")
                return {
                    "success": False,
                    "environment": custom_env,
                    "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                    "balance": 0,
                    "error": str(e)
                }
            
            if not account and not futures_account:
                return {
                    "success": False,
                    "environment": custom_env,
                    "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                    "balance": 0,
                    "error": "Failed to fetch account info"
                }
            
            # Try to get UM Account Detail for Portfolio Margin (more detailed)
            um_account_detail = None
            try:
                um_account_detail = await binance_service.get_um_account_detail()
            except Exception as e:
                logger.debug(f"UM account detail not available: {e}")
            
            # Extract balance info
            usdt_balance = 0
            if account_type == 'FUTURES' and futures_account:
                # Use Futures account balance
                usdt_balance = float(futures_account.get('availableBalance', 0))
                total_wallet_balance = float(futures_account.get('totalWalletBalance', 0))
                total_unrealized_pnl = float(futures_account.get('totalUnrealizedProfit', 0))
            else:
                # Use Spot account balance
                balances = account.get('balances', []) if account else []
                usdt_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDT'), 0)
                total_wallet_balance = usdt_balance
                total_unrealized_pnl = 0
            
            # Extract detailed info from UM account if available
            um_assets = um_account_detail.get('assets', []) if um_account_detail else []
            um_positions = um_account_detail.get('positions', []) if um_account_detail else []
            
            # Find USDT asset in UM account
            usdt_um_asset = next((a for a in um_assets if a.get('asset') == 'USDT'), None)
            
            # Calculate total wallet balance (cross wallet + unrealized PnL)
            available_balance = 0
            total_initial_margin = 0
            total_maint_margin = 0
            
            if usdt_um_asset:
                total_wallet_balance = float(usdt_um_asset.get('crossWalletBalance', 0))
                total_unrealized_pnl = float(usdt_um_asset.get('crossUnPnl', 0))
                total_initial_margin = float(usdt_um_asset.get('initialMargin', 0))
                total_maint_margin = float(usdt_um_asset.get('maintMargin', 0))
                # Available balance = wallet balance - initial margin
                available_balance = total_wallet_balance - total_initial_margin
            elif account_type == 'FUTURES' and futures_account:
                available_balance = float(futures_account.get('availableBalance', 0))
            
            # Count active positions
            active_positions = [p for p in um_positions if float(p.get('positionAmt', 0)) != 0]
            total_unrealized_profit = sum(float(p.get('unrealizedProfit', 0)) for p in active_positions)
            
            # Get permissions from account
            permissions = account.get('permissions', []) if account else []
            if futures_account:
                # Futures account doesn't have permissions field, but we know it's enabled
                if 'FUTURES' not in permissions:
                    permissions.append('FUTURES')
            
            response = {
                "success": True,
                "environment": custom_env,
                "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                "balance": usdt_balance,
                "account_type": account_type,
                "can_trade": account.get('canTrade', False) if account else True,
                "can_withdraw": account.get('canWithdraw', False) if account else False,
                "can_deposit": account.get('canDeposit', False) if account else False,
                "permissions": permissions,
                "has_portfolio_margin": um_account_detail is not None and len(um_assets) > 0,
            }
            
            # Add Portfolio Margin details if available
            if um_account_detail and usdt_um_asset:
                response.update({
                    "portfolio_margin": {
                        "total_wallet_balance": total_wallet_balance,
                        "total_unrealized_pnl": total_unrealized_pnl,
                        "available_balance": available_balance,
                        "total_initial_margin": total_initial_margin,
                        "total_maint_margin": total_maint_margin,
                        "active_positions_count": len(active_positions),
                        "total_unrealized_profit": total_unrealized_profit,
                        "assets": um_assets,
                        "positions": active_positions
                    }
                })
            
            return response
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
        logger.error(f"Failed to get account info: {e}")
        return {
            "success": False,
            "environment": env,
            "has_custom_keys": False,
            "balance": 0,
            "error": str(e)
        }


@router.post("/api-keys")
async def save_api_keys(
    settings_data: APIKeySettings,
    db: Session = Depends(get_db)
):
    """Save user's API keys (encrypted)"""
    try:
        user_id = 1  # Default user for now
        
        # Encrypt keys
        encrypted_key = encrypt_value(settings_data.binance_api_key)
        encrypted_secret = encrypt_value(settings_data.binance_api_secret)
        
        # Get or create API credentials
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if api_creds:
            # Update existing
            api_creds.binance_api_key = encrypted_key
            api_creds.binance_api_secret = encrypted_secret
            api_creds.environment = settings_data.environment
        else:
            # Create new
            api_creds = APICredential(
                user_id=user_id,
                binance_api_key=encrypted_key,
                binance_api_secret=encrypted_secret,
                environment=settings_data.environment
            )
            db.add(api_creds)
        
        db.commit()
        
        logger.info(f"API keys saved for user {user_id} (environment: {settings_data.environment})")
        
        return {
            "success": True,
            "message": "API keys saved successfully",
            "environment": settings_data.environment
        }
        
    except Exception as e:
        logger.error(f"Failed to save API keys: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api-keys")
async def delete_api_keys(db: Session = Depends(get_db)):
    """Delete user's custom API keys (revert to default)"""
    try:
        user_id = 1  # Default user for now
        
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if api_creds:
            db.delete(api_creds)
            db.commit()
            logger.info(f"API keys deleted for user {user_id}")
        
        return {
            "success": True,
            "message": "API keys removed, using default keys"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete API keys: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
async def get_current_settings(db: Session = Depends(get_db)):
    """Get current settings including decrypted keys for display"""
    try:
        user_id = 1  # Default user for now
        
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if api_creds and api_creds.binance_api_key:
            # User has custom keys - return decrypted values
            api_key = decrypt_value(api_creds.binance_api_key)
            api_secret = decrypt_value(api_creds.binance_api_secret)
            env_value = api_creds.environment or "demo"
            return {
                "success": True,
                "has_custom_keys": True,
                "environment": env_value,
                "api_key": api_key,  # Return full key for editing
                "api_secret": api_secret,  # Return full secret for editing
                "api_key_preview": f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
            }
        else:
            # Using default keys
            return {
                "success": True,
                "has_custom_keys": False,
                "environment": "demo",
                "api_key": "",
                "api_secret": "",
                "api_key_preview": "No custom keys"
            }
        
    except Exception as e:
        logger.error(f"Failed to get current settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

