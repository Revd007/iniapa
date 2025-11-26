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
        
        # Determine environment: prioritize request parameter over stored value
        # Normalize env parameter (handle case variations)
        env_lower = env.lower() if env else ''
        if env_lower in ['live', 'production', 'prod']:
            custom_env = 'live'
        elif env_lower in ['demo', 'test', 'testnet']:
            custom_env = 'demo'
        else:
            # Fallback to stored environment or default
            if api_creds and api_creds.environment:
                custom_env = api_creds.environment.lower()
                if custom_env not in ['demo', 'live']:
                    custom_env = 'demo'
            else:
                custom_env = 'demo'
        
        logger.info(f"Account info request - env param: {env}, custom_env: {custom_env}, has_api_creds: {bool(api_creds and api_creds.binance_api_key)}")
        
        if api_creds and api_creds.binance_api_key:
            # Use user's custom API keys
            api_key = decrypt_value(api_creds.binance_api_key)
            api_secret = decrypt_value(api_creds.binance_api_secret)
        else:
            # Use default keys from settings
            if custom_env == "demo":
                api_key = settings.BINANCE_DEMO_API_KEY
                api_secret = settings.BINANCE_DEMO_API_SECRET
            else:
                api_key = settings.BINANCE_LIVE_API_KEY
                api_secret = settings.BINANCE_LIVE_API_SECRET
        
        # Get binance service
        binance_service = request.app.state.binance_service
        
        # Temporarily override API keys and testnet mode if needed
        original_key = binance_service.api_key
        original_secret = binance_service.api_secret
        original_testnet = binance_service.testnet
        original_base_url = binance_service.base_url
        
        try:
            # Set API keys and testnet mode based on environment
            binance_service.api_key = api_key
            binance_service.api_secret = api_secret
            # Set testnet mode: demo = True (testnet), live = False (production)
            binance_service.testnet = (custom_env == 'demo')
            
            # Update base URL based on testnet mode - MUST be set before any requests
            # base_url is used when making requests, so we don't need to reinitialize session
            if binance_service.testnet:
                binance_service.base_url = settings.BINANCE_TESTNET_BASE_URL
            else:
                binance_service.base_url = "https://api.binance.com/api"
            
            # Only initialize session if it doesn't exist
            # Don't reinitialize if it exists to avoid "Connector is closed" errors
            if not binance_service.session:
                await binance_service.initialize()
            
            logger.info(f"Binance service configured - testnet: {binance_service.testnet}, base_url: {binance_service.base_url}, env: {custom_env}")
            
            # Get account info from Binance
            # Always try Futures account first (preferred for Futures trading)
            # If Futures fails, fallback to Spot account
            account = None
            futures_account = None
            account_type = 'SPOT'  # Default to SPOT, will be changed if Futures succeeds
            
            try:
                # Try Futures account first (preferred for Futures trading)
                try:
                    logger.info(f"🔄 Attempting to fetch Futures account for {custom_env} mode...")
                    futures_account = await binance_service.get_futures_account_info()
                    if futures_account:
                        account_type = 'FUTURES'
                        total_wallet = float(futures_account.get('totalWalletBalance', 0))
                        available = float(futures_account.get('availableBalance', 0))
                        logger.info(f"✅ Futures account detected! Total Balance: {total_wallet}, Available: {available}, Account Type: {account_type}")
                    else:
                        logger.warning("Futures account response is empty, falling back to Spot")
                except Exception as e:
                    logger.warning(f"⚠️ Futures account fetch failed: {e}")
                    logger.info("🔄 Falling back to Spot account...")
                
                # If Futures failed or empty, try Spot account
                # But don't overwrite account_type if Futures already succeeded
                if not futures_account:
                    try:
                        account = await binance_service.get_account()
                        logger.info(f"✅ Spot account info fetched successfully for {custom_env} mode")
                        permissions = account.get('permissions', [])
                        logger.info(f"Account permissions: {permissions}")
                        # Only set to SPOT if Futures didn't succeed
                        if account_type != 'FUTURES':
                            account_type = 'SPOT'
                            logger.info(f"📌 Account type set to SPOT (Futures not available)")
                    except Exception as e:
                        if futures_account:
                            # If we have Futures but Spot failed, that's okay - use Futures
                            logger.warning(f"Spot account fetch failed but we have Futures: {e}")
                            account_type = 'FUTURES'
                        else:
                            # Both failed
                            logger.error(f"❌ Both Futures and Spot account fetch failed: {e}")
                            raise
                else:
                    # Futures succeeded, but still try to get Spot account for permissions
                    try:
                        account = await binance_service.get_account()
                        permissions = account.get('permissions', [])
                        logger.info(f"✅ Spot account info fetched for permissions: {permissions}")
                        logger.info(f"📌 Account type remains FUTURES (Futures account available)")
                    except Exception as e:
                        logger.warning(f"Spot account fetch failed but we have Futures: {e}")
                        account = None
            except Exception as e:
                logger.error(f"❌ Failed to fetch account info: {e}", exc_info=True)
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
            total_wallet_balance = 0
            total_unrealized_pnl = 0
            
            if account_type == 'FUTURES' and futures_account:
                # Use Futures account balance
                usdt_balance = float(futures_account.get('availableBalance', 0))
                total_wallet_balance = float(futures_account.get('totalWalletBalance', 0))
                total_unrealized_pnl = float(futures_account.get('totalUnrealizedProfit', 0))
                logger.info(f"💰 Futures balance extracted: Available={usdt_balance}, Total={total_wallet_balance}, Unrealized PnL={total_unrealized_pnl}")
            elif account:
                # Use Spot account balance
                balances = account.get('balances', []) if account else []
                usdt_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDT'), 0)
                total_wallet_balance = usdt_balance
                total_unrealized_pnl = 0
                logger.info(f"💰 Spot balance extracted: USDT={usdt_balance}, Total balances count={len(balances)}")
                # Log all balances for debugging
                if balances:
                    logger.debug(f"All balances: {[(b['asset'], b['free']) for b in balances[:5]]}")  # Log first 5
            else:
                logger.warning("⚠️ No account data available to extract balance")
            
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
            
            # Log final account type and balance for debugging
            logger.info(f"📊 Final account info - Type: {account_type}, Balance: {usdt_balance}, Environment: {custom_env}")
            
            response = {
                "success": True,
                "environment": custom_env,
                "has_custom_keys": bool(api_creds and api_creds.binance_api_key),
                "balance": usdt_balance,
                "account_type": account_type,  # FUTURES or SPOT
                "can_trade": account.get('canTrade', False) if account else True,
                "can_withdraw": account.get('canWithdraw', False) if account else False,
                "can_deposit": account.get('canDeposit', False) if account else False,
                "permissions": permissions,
                "has_portfolio_margin": um_account_detail is not None and len(um_assets) > 0,
            }
            
            logger.info(f"📤 Returning response - account_type: {response['account_type']}, balance: {response['balance']}")
            
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
            # Just restore the values - don't reinitialize session to avoid "Connector is closed" errors
            binance_service.api_key = original_key
            binance_service.api_secret = original_secret
            binance_service.testnet = original_testnet
            binance_service.base_url = original_base_url
        
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

