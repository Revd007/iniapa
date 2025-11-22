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
            custom_env = api_creds.environment or env
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
        
        # Temporarily override API keys if needed
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        
        try:
            if api_creds:
                binance_service.api_key = api_key
                binance_service.api_secret = api_secret
            
            # Get account info from Binance
            account = await binance_service.get_account()
            
            if not account:
                return {
                    "success": False,
                    "environment": custom_env,
                    "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                    "balance": 0,
                    "error": "Failed to fetch account info"
                }
            
            # Extract balance info
            balances = account.get('balances', [])
            usdt_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDT'), 0)
            
            return {
                "success": True,
                "environment": custom_env,
                "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                "balance": usdt_balance,
                "account_type": account.get('accountType', 'SPOT'),
                "can_trade": account.get('canTrade', False),
                "can_withdraw": account.get('canWithdraw', False),
                "can_deposit": account.get('canDeposit', False),
                "permissions": account.get('permissions', [])
            }
        finally:
            # Restore original keys
            binance_service.api_key = original_key
            binance_service.api_secret = original_secret
        
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
    """Get current settings (without exposing actual keys)"""
    try:
        user_id = 1  # Default user for now
        
        api_creds = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if api_creds and api_creds.binance_api_key:
            # User has custom keys
            key = decrypt_value(api_creds.binance_api_key)
            return {
                "success": True,
                "has_custom_keys": True,
                "environment": api_creds.environment or "demo",
                "api_key_preview": f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
            }
        else:
            # Using default keys
            return {
                "success": True,
                "has_custom_keys": False,
                "environment": "demo" if settings.BINANCE_TESTNET else "live",
                "api_key_preview": "Using default keys"
            }
        
    except Exception as e:
        logger.error(f"Failed to get current settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

