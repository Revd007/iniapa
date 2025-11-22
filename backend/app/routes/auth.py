"""
OAuth Authentication Routes
Handles Binance and MT5 broker authentication flow
Clean architecture following OAuth 2.0 best practices
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging

from app.database import get_db
from app.services.auth_service import auth_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Request/Response Models
# ============================================

class LoginInitResponse(BaseModel):
    """Response for OAuth login initialization"""
    authorization_url: str
    state: str


class CallbackRequest(BaseModel):
    """OAuth callback payload"""
    code: str
    state: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfoResponse(BaseModel):
    """Authenticated user info"""
    user_id: int
    email: str
    username: str
    broker: Optional[str]
    balance: Optional[float]
    currency: Optional[str]


# ============================================
# Binance OAuth Flow
# ============================================

@router.get("/binance/login", response_model=LoginInitResponse)
async def binance_login_init(request: Request):
    """
    Step 1: Initialize Binance OAuth flow
    Generate authorization URL and PKCE challenge
    
    Frontend should:
    1. Call this endpoint
    2. Store state and code_verifier in sessionStorage
    3. Redirect user to authorization_url
    """
    # Generate PKCE parameters
    state = auth_service.generate_state()
    code_verifier = auth_service.generate_code_verifier()
    code_challenge = auth_service.generate_code_challenge(code_verifier)
    
    # Store in session for later verification
    request.session['oauth_state'] = state
    request.session['code_verifier'] = code_verifier
    
    # Generate Binance authorization URL
    auth_url = auth_service.get_binance_authorization_url(
        state=state,
        code_challenge=code_challenge,
        scopes=['user:openId', 'user:email', 'user:apiKey', 'trade']
    )
    
    logger.info(f"Generated Binance OAuth URL for new login")
    
    return {
        "authorization_url": auth_url,
        "state": state
    }


@router.get("/binance/callback")
async def binance_callback(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Step 2: Handle OAuth callback from Binance
    Exchange authorization code for tokens and create user session
    
    This endpoint is called by Binance after user authorizes
    """
    # Verify state to prevent CSRF
    stored_state = request.session.get('oauth_state')
    if not stored_state or stored_state != state:
        logger.error(f"State mismatch: {state} != {stored_state}")
        raise HTTPException(status_code=400, detail="Invalid state parameter (CSRF protection)")
    
    # Get code verifier from session
    code_verifier = request.session.get('code_verifier')
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Code verifier not found in session")
    
    try:
        # Exchange code for tokens
        tokens = await auth_service.exchange_code_for_tokens(code, code_verifier)
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        expires_in = tokens['expires_in']
        
        # Get user info from Binance
        user_info = await auth_service.get_user_info(access_token)
        email = user_info['email']
        binance_user_id = user_info['userId']
        
        # Get or create user in our database
        user = auth_service.get_or_create_user(db, email, binance_user_id)
        
        # Store Binance OAuth tokens
        auth_service.store_user_credentials(
            db,
            user.id,
            access_token,
            refresh_token,
            expires_in
        )
        
        # Fetch account balance
        try:
            account_info = await auth_service.get_account_info(access_token)
            # Store balance in API credentials
            from app.models import APICredential
            cred = db.query(APICredential).filter_by(user_id=user.id).first()
            if cred and 'balances' in account_info:
                usdt_balance = next((b['free'] for b in account_info['balances'] if b['asset'] == 'USDT'), 0)
                cred.broker_name = 'binance'
                cred.account_balance = float(usdt_balance)
                cred.account_currency = 'USDT'
                from datetime import datetime
                cred.last_balance_update = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to fetch account balance: {e}")
        
        # Create internal JWT tokens for our API
        internal_access = auth_service.create_access_token(user.id)
        internal_refresh = auth_service.create_refresh_token(user.id)
        
        # Clear OAuth session data
        request.session.pop('oauth_state', None)
        request.session.pop('code_verifier', None)
        
        # Redirect to frontend with tokens
        frontend_url = f"http://localhost:3000/auth/success?access_token={internal_access}&refresh_token={internal_refresh}"
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout user by clearing session
    Frontend should also clear stored tokens
    """
    request.session.clear()
    logger.info("User logged out")
    return {"success": True, "message": "Logged out successfully"}


# ============================================
# Token Management
# ============================================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """
    Refresh expired access token using refresh token
    """
    user_id = auth_service.verify_token(refresh_token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Create new access token
    new_access_token = auth_service.create_access_token(user_id)
    new_refresh_token = auth_service.create_refresh_token(user_id)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


# ============================================
# User Info
# ============================================

@router.get("/me", response_model=UserInfoResponse)
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user info
    Requires valid JWT token in Authorization header
    """
    # Extract token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(' ')[1]
    user_id = auth_service.verify_token(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Get user from database
    from app.models import User, APICredential
    user = db.query(User).filter_by(id=user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get credentials for balance info
    cred = db.query(APICredential).filter_by(user_id=user_id).first()
    
    return {
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "broker": cred.broker_name if cred else None,
        "balance": cred.account_balance if cred else None,
        "currency": cred.account_currency if cred else None
    }


# ============================================
# Account Balance Refresh
# ============================================

@router.post("/refresh-balance")
async def refresh_account_balance(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Manually refresh account balance from broker
    Fetches latest balance from Binance using OAuth token
    """
    # Get current user
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = auth_header.split(' ')[1]
    user_id = auth_service.verify_token(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        # Get valid Binance access token (auto-refresh if needed)
        binance_token = await auth_service.ensure_valid_token(db, user_id)
        
        # Fetch account info
        account_info = await auth_service.get_account_info(binance_token)
        
        # Update balance in database
        from app.models import APICredential
        from datetime import datetime
        
        cred = db.query(APICredential).filter_by(user_id=user_id).first()
        if cred and 'balances' in account_info:
            usdt_balance = next((b['free'] for b in account_info['balances'] if b['asset'] == 'USDT'), 0)
            cred.account_balance = float(usdt_balance)
            cred.last_balance_update = datetime.utcnow()
            db.commit()
            
            logger.info(f"Refreshed balance for user {user_id}: {usdt_balance} USDT")
            
            return {
                "success": True,
                "balance": float(usdt_balance),
                "currency": "USDT",
                "broker": "binance"
            }
        
        raise HTTPException(status_code=500, detail="Failed to fetch balance")
        
    except Exception as e:
        logger.error(f"Balance refresh error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh balance: {str(e)}")

