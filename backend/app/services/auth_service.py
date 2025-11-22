"""
OAuth Authentication Service
Handles Binance OAuth 2.0 and MT5 authentication flow
Clean implementation following official Binance OAuth documentation
"""

import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
try:
    from jose import JWTError, jwt
except ImportError:
    # Fallback jika python-jose belum terinstall
    try:
        from jose.jwt import JWTError, jwt
    except ImportError:
        # Use built-in jwt jika jose tidak tersedia
        import jwt as pyjwt
        JWTError = Exception
        jwt = pyjwt
import aiohttp
import logging

from app.config import settings
from app.models import User, APICredential
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AuthService:
    """
    Production OAuth service for Binance and MT5 broker authentication
    Implements OAuth 2.0 Authorization Code Flow with PKCE
    """
    
    def __init__(self):
        self.binance_oauth_url = "https://accounts.binance.com"
        self.binance_api_url = "https://www.binanceapis.com"
        self.client_id = settings.BINANCE_OAUTH_CLIENT_ID
        self.client_secret = settings.BINANCE_OAUTH_CLIENT_SECRET
        self.redirect_uri = settings.BINANCE_OAUTH_REDIRECT_URI
    
    # ============================================
    # OAuth 2.0 - Authorization Code Flow
    # ============================================
    
    def generate_state(self) -> str:
        """Generate CSRF token for OAuth state parameter"""
        return secrets.token_urlsafe(32)
    
    def generate_code_verifier(self) -> str:
        """Generate PKCE code verifier (43-128 chars)"""
        return secrets.token_urlsafe(64)
    
    def generate_code_challenge(self, code_verifier: str) -> str:
        """
        Generate PKCE code challenge from verifier
        SHA256 hash -> base64url encode
        """
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        b64 = base64.urlsafe_b64encode(digest).decode('utf-8')
        return b64.rstrip('=')  # Remove padding
    
    def get_binance_authorization_url(
        self, 
        state: str, 
        code_challenge: str,
        scopes: list = None
    ) -> str:
        """
        Step 1: Generate Binance OAuth authorization URL
        User will be redirected here to login with their Binance account
        """
        if scopes is None:
            scopes = ['user:openId', 'user:email', 'user:apiKey', 'trade']
        
        scope_str = ','.join(scopes)
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'state': state,
            'scope': scope_str,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        auth_url = f"{self.binance_oauth_url}/en/oauth/authorize?{query_string}"
        
        logger.info(f"Generated Binance OAuth URL for state: {state[:10]}...")
        return auth_url
    
    async def exchange_code_for_tokens(
        self, 
        authorization_code: str, 
        code_verifier: str
    ) -> Dict:
        """
        Step 2: Exchange authorization code for access/refresh tokens
        Called after user authorizes on Binance and is redirected back
        """
        token_url = f"{self.binance_oauth_url}/oauth/token"
        
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'client_id': self.client_id,
            'code_verifier': code_verifier,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed: {error_text}")
                        raise Exception(f"Failed to exchange code: {error_text}")
                    
                    tokens = await response.json()
                    logger.info("Successfully exchanged authorization code for tokens")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            raise
    
    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh expired access token using refresh token
        Called automatically when access token expires
        """
        token_url = f"{self.binance_oauth_url}/oauth/token"
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed: {error_text}")
                        raise Exception(f"Failed to refresh token: {error_text}")
                    
                    tokens = await response.json()
                    logger.info("Successfully refreshed access token")
                    return tokens
                    
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict:
        """
        Step 3: Fetch authenticated user information from Binance
        Returns user email, userId, and account details
        """
        user_info_url = f"{self.binance_api_url}/oauth-api/v1/user-info"
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(user_info_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get user info: {error_text}")
                        raise Exception(f"Failed to get user info: {error_text}")
                    
                    data = await response.json()
                    
                    if not data.get('success'):
                        raise Exception(f"User info request failed: {data.get('message')}")
                    
                    user_data = data.get('data', {})
                    logger.info(f"Successfully fetched user info for: {user_data.get('email')}")
                    return user_data
                    
        except Exception as e:
            logger.error(f"Get user info error: {e}")
            raise
    
    async def get_account_info(self, access_token: str) -> Dict:
        """
        Fetch user's Binance account information (balance, assets, etc)
        Uses OAuth access token for authenticated API calls
        """
        account_url = f"{self.binance_api_url}/oauth-api/v1/account"
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(account_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get account info: {error_text}")
                        raise Exception(f"Failed to get account info: {error_text}")
                    
                    data = await response.json()
                    logger.info("Successfully fetched account information")
                    return data.get('data', {})
                    
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            raise
    
    # ============================================
    # JWT Token Management (Internal)
    # ============================================
    
    def create_access_token(self, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create internal JWT access token for API authentication
        Separate from Binance OAuth tokens
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.utcnow() + expires_delta
        to_encode = {
            'sub': str(user_id),
            'exp': expire,
            'type': 'access'
        }
        
        # Handle both python-jose and pyjwt
        if hasattr(jwt, 'encode'):
            encoded_jwt = jwt.encode(
                to_encode, 
                settings.JWT_SECRET_KEY, 
                algorithm=settings.JWT_ALGORITHM
            )
        else:
            # Fallback untuk pyjwt
            encoded_jwt = jwt.encode(
                to_encode,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM
            )
        
        return encoded_jwt
    
    def create_refresh_token(self, user_id: int) -> str:
        """Create internal JWT refresh token"""
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {
            'sub': str(user_id),
            'exp': expire,
            'type': 'refresh'
        }
        
        # Handle both python-jose and pyjwt
        if hasattr(jwt, 'encode'):
            encoded_jwt = jwt.encode(
                to_encode, 
                settings.JWT_SECRET_KEY, 
                algorithm=settings.JWT_ALGORITHM
            )
        else:
            # Fallback untuk pyjwt
            encoded_jwt = jwt.encode(
                to_encode,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM
            )
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[int]:
        """
        Verify JWT token and extract user_id
        Returns user_id if valid, None if invalid/expired
        """
        try:
            # Handle both python-jose and pyjwt
            if hasattr(jwt, 'decode'):
                payload = jwt.decode(
                    token, 
                    settings.JWT_SECRET_KEY, 
                    algorithms=[settings.JWT_ALGORITHM]
                )
            else:
                # Fallback untuk pyjwt
                payload = jwt.decode(
                    token,
                    settings.JWT_SECRET_KEY,
                    algorithms=[settings.JWT_ALGORITHM]
                )
            user_id: str = payload.get('sub')
            if user_id is None:
                return None
            return int(user_id)
        except (JWTError, Exception):
            return None
    
    # ============================================
    # User Management
    # ============================================
    
    def get_or_create_user(
        self, 
        db: Session, 
        email: str, 
        binance_user_id: str
    ) -> User:
        """
        Get existing user or create new one from Binance OAuth
        Links Binance account to internal user account
        """
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            logger.info(f"User exists: {email}")
            return user
        
        # Create new user
        username = email.split('@')[0]
        user = User(
            email=email,
            username=username,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Created new user: {email}")
        return user
    
    def store_user_credentials(
        self, 
        db: Session, 
        user_id: int,
        binance_access_token: str,
        binance_refresh_token: str,
        token_expires_in: int
    ):
        """
        Store user's Binance OAuth tokens securely
        Tokens are used for authenticated API calls on behalf of user
        """
        credential = db.query(APICredential).filter_by(user_id=user_id).first()
        
        token_expires_at = datetime.utcnow() + timedelta(seconds=token_expires_in)
        
        if credential:
            # Update existing
            credential.binance_access_token = binance_access_token
            credential.binance_refresh_token = binance_refresh_token
            credential.binance_token_expires_at = token_expires_at
            credential.updated_at = datetime.utcnow()
        else:
            # Create new
            credential = APICredential(
                user_id=user_id,
                binance_access_token=binance_access_token,
                binance_refresh_token=binance_refresh_token,
                binance_token_expires_at=token_expires_at
            )
            db.add(credential)
        
        db.commit()
        logger.info(f"Stored credentials for user {user_id}")
    
    async def ensure_valid_token(self, db: Session, user_id: int) -> str:
        """
        Ensure user has valid Binance access token
        Auto-refresh if expired
        Returns valid access token
        """
        credential = db.query(APICredential).filter_by(user_id=user_id).first()
        
        if not credential:
            raise Exception("User credentials not found")
        
        # Check if token is still valid
        if credential.binance_token_expires_at and \
           credential.binance_token_expires_at > datetime.utcnow():
            return credential.binance_access_token
        
        # Token expired, refresh it
        logger.info(f"Token expired for user {user_id}, refreshing...")
        
        tokens = await self.refresh_access_token(credential.binance_refresh_token)
        
        # Update stored tokens
        self.store_user_credentials(
            db,
            user_id,
            tokens['access_token'],
            tokens.get('refresh_token', credential.binance_refresh_token),
            tokens['expires_in']
        )
        
        return tokens['access_token']


# Global auth service instance
auth_service = AuthService()

