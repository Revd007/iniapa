"""
Binance Service - Enhanced with exchange info and 24h tickers
Production-ready with proper error handling and rate limiting
"""

import hashlib
import hmac
import time
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode
from collections import deque
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)


class BinanceService:
    """
    Service for interacting with Binance API with rate limiting
    
    Rate Limits (per Binance documentation):
    - Request weight: 1200 per minute (20 per second)
    - Order limits: 50 per 10 seconds
    - Raw requests: 6000 per 5 minutes
    
    This service implements a token bucket algorithm to prevent IP bans
    """
    
    def __init__(self):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.testnet = settings.BINANCE_TESTNET
        
        if self.testnet:
            self.base_url = settings.BINANCE_TESTNET_BASE_URL
        else:
            self.base_url = "https://api.binance.com/api"
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting: Token bucket implementation
        # Binance allows 1200 weight per minute, we use 600 to be very safe
        # Conservative limit prevents IP bans and ensures reliable service
        self.max_requests_per_minute = 600  # Reduced from 1000 for safety
        self.request_timestamps = deque()  # Track request timestamps
        self.rate_limit_lock = asyncio.Lock()  # Ensure thread safety
        
        # Logging throttling to prevent spam
        self._last_log_time = None
        self._log_interval = 10.0  # Only log rate limit warnings every 10 seconds max
        
        # Circuit breaker for geolocation restriction
        # Once detected, stop making requests for a period to prevent spam
        self._geolocation_blocked = False
        self._geolocation_blocked_until = None
        self._geolocation_block_duration = 300  # Block for 5 minutes after detection
    
    async def initialize(self):
        """Initialize aiohttp session"""
        import ssl
        # Create SSL context that doesn't verify certificates for local development
        # WARNING: Only use this for testing/development with ISP/proxy issues
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        logger.info(f"Binance service initialized ({'TESTNET' if self.testnet else 'LIVE'})")
    
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _wait_for_rate_limit(self, weight: int = 1):
        """
        Rate limiting implementation using token bucket algorithm
        Ensures we don't exceed Binance's rate limits
        
        Args:
            weight: API request weight (default 1, some endpoints use more)
        """
        async with self.rate_limit_lock:
            now = datetime.now()
            # Remove timestamps older than 1 minute
            while self.request_timestamps and self.request_timestamps[0] < now - timedelta(minutes=1):
                self.request_timestamps.popleft()
            
            # Check if we need to wait
            current_count = len(self.request_timestamps)
            if current_count >= self.max_requests_per_minute:
                # Calculate how long to wait
                oldest_timestamp = self.request_timestamps[0]
                wait_until = oldest_timestamp + timedelta(minutes=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    # Only log if waiting more than 0.5 seconds AND haven't logged recently
                    should_log = (
                        wait_seconds > 0.5 and 
                        (self._last_log_time is None or 
                         (now - self._last_log_time).total_seconds() >= self._log_interval)
                    )
                    
                    if should_log:
                        logger.warning(
                            f"Rate limit reached ({current_count}/{self.max_requests_per_minute} requests/min). "
                            f"Waiting {wait_seconds:.2f}s to avoid IP ban..."
                        )
                        self._last_log_time = now
                    else:
                        # Use debug level for frequent small waits
                        logger.debug(f"Rate limit: waiting {wait_seconds:.2f}s (suppressed frequent logs)")
                    
                    await asyncio.sleep(wait_seconds)
                    # Clean up old timestamps after waiting
                    now = datetime.now()
                    while self.request_timestamps and self.request_timestamps[0] < now - timedelta(minutes=1):
                        self.request_timestamps.popleft()
            
            # Add current request timestamp (with weight consideration)
            for _ in range(weight):
                self.request_timestamps.append(now)
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        signed: bool = False,
        weight: int = 1
    ) -> Dict:
        """
        Make request to Binance API with rate limiting
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            signed: Whether request needs signature
            weight: API weight for rate limiting (default 1)
        """
        # Check circuit breaker for geolocation restriction
        if self._geolocation_blocked:
            now = datetime.now()
            if self._geolocation_blocked_until and now < self._geolocation_blocked_until:
                # Still blocked, raise early to prevent unnecessary requests
                raise Exception(
                    "Binance API is not available in your location. "
                    "This is a geolocation restriction by Binance. "
                    "Solutions: 1) Use a VPN to connect from an allowed location, "
                    "2) Use testnet mode if available, "
                    "3) Contact Binance support if you believe this is an error. "
                    f"(Circuit breaker active until {self._geolocation_blocked_until.strftime('%H:%M:%S')})"
                )
            else:
                # Block period expired, reset circuit breaker
                self._geolocation_blocked = False
                self._geolocation_blocked_until = None
        
        # Apply rate limiting before making request
        await self._wait_for_rate_limit(weight)
        
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        # Validate URL - ensure we're not being redirected
        if 'internet-positif' in url.lower() or 'binance' not in url.lower():
            logger.error(f"⚠️ Invalid URL detected: {url}. This might indicate DNS hijacking or ISP blocking.")
            raise Exception("Invalid API URL detected. This might indicate DNS hijacking or ISP blocking. Please check your network settings or use VPN.")
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            async with self.session.request(method, url, params=params, headers=headers, timeout=30, allow_redirects=False) as response:
                # Check if we got redirected (ISP blocking)
                if response.status in [301, 302, 303, 307, 308]:
                    redirect_url = response.headers.get('Location', '')
                    logger.error(f"⚠️ ISP Blocking detected! Redirected to: {redirect_url}")
                    raise Exception(f"ISP blocking detected: Binance is blocked by your ISP/network. Please use VPN or contact your network administrator.")
                
                # Check content type - if HTML, means we got blocked/redirected
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type.lower():
                    # Try to read response to see what we got
                    text = await response.text()
                    if 'internet-positif' in text.lower() or 'internet-positif' in str(response.url).lower():
                        logger.error(f"⚠️ ISP Blocking detected! Got HTML response instead of JSON. URL: {response.url}")
                        raise Exception("ISP blocking detected: Binance is blocked by your ISP (redirected to internet-positif.info). Please use VPN or contact your network administrator.")
                    else:
                        logger.error(f"⚠️ Unexpected HTML response from: {response.url}")
                        raise Exception(f"Unexpected response format. Expected JSON but got HTML. This might indicate ISP blocking or network issues.")
                
                # Try to parse JSON
                try:
                    data = await response.json()
                except Exception as json_error:
                    # If JSON parsing fails, log the actual response
                    text = await response.text()
                    logger.error(f"Failed to parse JSON response. Status: {response.status}, URL: {response.url}, Response preview: {text[:200]}")
                    raise Exception(f"Invalid JSON response from Binance API. This might indicate ISP blocking or network issues.")
                
                if response.status != 200:
                    # Check if it's a rate limit error
                    if response.status == 429:
                        logger.error(
                            "⚠️ Binance rate limit exceeded (429)! "
                            "Waiting 60 seconds before retry to prevent IP ban..."
                        )
                        await asyncio.sleep(60)
                        # Clear request history to reset rate limit tracking
                        async with self.rate_limit_lock:
                            self.request_timestamps.clear()
                        return await self._request(method, endpoint, params, signed, weight)
                    
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', 'N/A')
                    
                    # Check for IP/permission restriction error (-2015)
                    if error_code == -2015 or ('IP' in error_msg and 'permissions' in error_msg.lower()):
                        logger.error(f"⚠️ Binance API IP/Permission error [{error_code}]: {error_msg}")
                        raise Exception(
                            f"Binance API error: {error_msg}. "
                            "Possible causes: 1) Your VPN IP is not whitelisted in Binance API settings, "
                            "2) API key doesn't have required permissions enabled, "
                            "3) IP restriction is enabled but your current IP is not in the whitelist. "
                            "Please check your Binance API settings (https://www.binance.com/en/my/settings/api-management) "
                            "and add your VPN IP to the whitelist, or disable IP restriction."
                        )
                    
                    # Check for restricted location error (geolocation blocking)
                    if 'restricted location' in error_msg.lower() or 'eligibility' in error_msg.lower():
                        # Activate circuit breaker to prevent spam retries
                        self._geolocation_blocked = True
                        self._geolocation_blocked_until = datetime.now() + timedelta(seconds=self._geolocation_block_duration)
                        logger.error(
                            f"⚠️ Binance geolocation restriction [{error_code}]: {error_msg}. "
                            f"Circuit breaker activated for {self._geolocation_block_duration}s to prevent spam retries."
                        )
                        raise Exception(
                            "Binance API is not available in your location. "
                            "This is a geolocation restriction by Binance. "
                            "Solutions: 1) Use a VPN to connect from an allowed location, "
                            "2) Use testnet mode if available, "
                            "3) Contact Binance support if you believe this is an error."
                        )
                    
                    logger.error(f"Binance API error [{error_code}]: {error_msg}")
                    raise Exception(f"Binance API error: {error_msg}")
                
                return data
                
        except aiohttp.ClientError as e:
            error_str = str(e)
            if 'internet-positif' in error_str.lower():
                logger.error(f"⚠️ ISP Blocking detected in error: {error_str}")
                raise Exception("ISP blocking detected: Binance is blocked by your ISP. Please use VPN or contact your network administrator.")
            logger.error(f"Network error: {error_str}, URL: {url}")
            raise Exception(f"Network error: {error_str}")
        except Exception as e:
            error_str = str(e)
            if 'ISP blocking' in error_str or 'internet-positif' in error_str.lower():
                raise
            logger.error(f"Request failed: {error_str}, URL: {url}")
            raise
    
    async def get_ticker_price(self, symbol: str) -> Dict:
        """Get current price for a symbol"""
        return await self._request("GET", "/v3/ticker/price", {"symbol": symbol})
    
    async def get_24h_ticker(self, symbol: str) -> Dict:
        """Get 24h ticker data for a symbol (weight: 1)"""
        return await self._request("GET", "/v3/ticker/24hr", {"symbol": symbol}, weight=1)
    
    async def get_24h_tickers(self) -> List[Dict]:
        """
        Get 24h ticker data for ALL symbols (weight: 40)
        
        This endpoint returns all tickers at once, which is more efficient
        than fetching individual tickers. However, it has higher weight.
        """
        return await self._request("GET", "/v3/ticker/24hr", weight=40)
    
    async def get_exchange_info(self) -> Dict:
        """Get exchange trading rules and symbol information (weight: 10)"""
        return await self._request("GET", "/v3/exchangeInfo", weight=10)
    
    async def get_klines(
        self, 
        symbol: str, 
        interval: str, 
        limit: int = 500
    ) -> List:
        """Get kline/candlestick data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000)  # Binance max is 1000
        }
        return await self._request("GET", "/v3/klines", params)
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """Create an order on Binance"""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        
        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = "GTC"
        
        try:
            order = await self._request("POST", "/v3/order", params, signed=True)
            
            # Create SL/TP orders if specified
            result = {"main_order": order}
            
            if stop_loss:
                sl_params = {
                    "symbol": symbol,
                    "side": "SELL" if side == "BUY" else "BUY",
                    "type": "STOP_LOSS_LIMIT",
                    "quantity": quantity,
                    "price": stop_loss,
                    "stopPrice": stop_loss,
                    "timeInForce": "GTC"
                }
                result["stop_loss_order"] = await self._request("POST", "/v3/order", sl_params, signed=True)
            
            if take_profit:
                tp_params = {
                    "symbol": symbol,
                    "side": "SELL" if side == "BUY" else "BUY",
                    "type": "TAKE_PROFIT_LIMIT",
                    "quantity": quantity,
                    "price": take_profit,
                    "stopPrice": take_profit,
                    "timeInForce": "GTC"
                }
                result["take_profit_order"] = await self._request("POST", "/v3/order", tp_params, signed=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create order: {str(e)}")
            raise
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an order on Binance"""
        try:
            params = {
                "symbol": symbol,
                "orderId": order_id
            }
            data = await self._request("DELETE", "/v3/order", params, signed=True)
            logger.info(f"Order {order_id} cancelled for {symbol}")
            return data
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id} for {symbol}: {str(e)}")
            raise
    
    async def get_account_info(self) -> Dict:
        """Get account information (Spot)"""
        return await self._request("GET", "/v3/account", signed=True)
    
    async def get_futures_account_info(self) -> Dict:
        """
        Get Futures account information
        Reference: https://binance-docs.github.io/apidocs/futures/en/#account-information-v2-user_data
        """
        if self.testnet:
            # Testnet Futures uses different endpoint
            futures_base_url = "https://testnet.binancefuture.com"
        else:
            futures_base_url = "https://fapi.binance.com"
        
        # Apply rate limiting
        await self._wait_for_rate_limit(5)  # Futures account endpoint weight: 5
        
        if not self.session:
            await self.initialize()
        
        url = f"{futures_base_url}/fapi/v2/account"
        params = {}
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        # Add signature
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generate_signature(params)
        
        try:
            async with self.session.request("GET", url, params=params, headers=headers, timeout=30, allow_redirects=False) as response:
                if response.status in [301, 302, 303, 307, 308]:
                    redirect_url = response.headers.get('Location', '')
                    logger.error(f"⚠️ ISP Blocking in Futures! Redirected to: {redirect_url}")
                    raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type.lower():
                    text = await response.text()
                    if 'internet-positif' in text.lower():
                        logger.error(f"⚠️ ISP Blocking in Futures! URL: {response.url}")
                        raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                    raise Exception(f"Unexpected HTML response from Futures API: {response.url}")
                
                try:
                    data = await response.json()
                except Exception as json_error:
                    text = await response.text()
                    logger.error(f"Failed to parse JSON from Futures. Response: {text[:200]}")
                    raise Exception(f"Invalid JSON response from Futures API.")
                
                if response.status != 200:
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', 'N/A')
                    
                    # Check for IP restriction error
                    if error_code == -2015 or 'IP' in error_msg or 'permissions' in error_msg.lower():
                        logger.error(f"⚠️ Binance API IP/Permission error [{error_code}]: {error_msg}")
                        raise Exception(
                            f"Binance API error: {error_msg}. "
                            "Possible causes: 1) Your VPN IP is not whitelisted in Binance API settings, "
                            "2) API key doesn't have Futures permission enabled, "
                            "3) IP restriction is enabled but your current IP is not in the whitelist. "
                            "Please check your Binance API settings and add your VPN IP to the whitelist."
                        )
                    
                    logger.error(f"Futures API error [{error_code}]: {error_msg}")
                    raise Exception(f"Futures API error: {error_msg}")
                
                return data
        except Exception as e:
            error_str = str(e)
            if 'ISP blocking' in error_str or 'IP' in error_str:
                raise
            logger.error(f"Futures request failed: {error_str}, URL: {url}")
            raise
    
    async def get_account(self) -> Dict:
        """Alias for get_account_info (for compatibility)"""
        return await self.get_account_info()
    
    async def _portfolio_margin_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False,
        weight: int = 1
    ) -> Dict:
        """
        Make request to Binance Portfolio Margin API
        Portfolio Margin uses different base URL: https://fapi.binance.com or https://api.binance.com
        """
        if self.testnet:
            # Testnet doesn't support Portfolio Margin, use spot account as fallback
            if endpoint == "/papi/v1/account":
                return await self.get_account_info()
            elif endpoint == "/papi/v1/balance":
                account = await self.get_account_info()
                balances = account.get('balances', [])
                if params and params.get('asset'):
                    asset = params['asset']
                    balance = next((b for b in balances if b['asset'] == asset), None)
                    return balance if balance else {}
                return balances
            else:
                return {}
        
        # Portfolio Margin API uses https://fapi.binance.com base URL
        portfolio_base_url = "https://fapi.binance.com"
        
        # Apply rate limiting
        await self._wait_for_rate_limit(weight)
        
        if not self.session:
            await self.initialize()
        
        url = f"{portfolio_base_url}{endpoint}"
        params = params or {}
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        # Validate URL
        if 'internet-positif' in url.lower() or 'binance' not in url.lower():
            logger.error(f"⚠️ Invalid Portfolio Margin URL: {url}")
            raise Exception("Invalid Portfolio Margin API URL. This might indicate DNS hijacking or ISP blocking.")
        
        try:
            async with self.session.request(method, url, params=params, headers=headers, timeout=30, allow_redirects=False) as response:
                if response.status in [301, 302, 303, 307, 308]:
                    redirect_url = response.headers.get('Location', '')
                    logger.error(f"⚠️ ISP Blocking in Portfolio Margin! Redirected to: {redirect_url}")
                    raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type.lower():
                    text = await response.text()
                    if 'internet-positif' in text.lower():
                        logger.error(f"⚠️ ISP Blocking in Portfolio Margin! URL: {response.url}")
                        raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                    # Check if it's an error page or redirect
                    if 'error' in text.lower() or 'not found' in text.lower() or '403' in text or '401' in text:
                        logger.warning(f"Portfolio Margin returned HTML error page. This might indicate: 1) Account doesn't have Portfolio Margin enabled, 2) IP restriction, 3) Permission issue. URL: {response.url}")
                        # Return empty structure instead of raising error
                        return {
                            "assets": [],
                            "positions": []
                        }
                    raise Exception(f"Unexpected HTML response from Portfolio Margin: {response.url}")
                
                try:
                    data = await response.json()
                except Exception as json_error:
                    text = await response.text()
                    logger.error(f"Failed to parse JSON from Portfolio Margin. Response: {text[:200]}")
                    raise Exception(f"Invalid JSON response from Portfolio Margin API.")
                
                if response.status != 200:
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', 'N/A')
                    
                    # Check for restricted location error (geolocation blocking)
                    if 'restricted location' in error_msg.lower() or 'eligibility' in error_msg.lower():
                        # Activate circuit breaker
                        self._geolocation_blocked = True
                        self._geolocation_blocked_until = datetime.now() + timedelta(seconds=self._geolocation_block_duration)
                        logger.error(
                            f"⚠️ Binance geolocation restriction in Portfolio Margin [{error_code}]: {error_msg}. "
                            f"Circuit breaker activated for {self._geolocation_block_duration}s."
                        )
                        raise Exception(
                            "Binance API is not available in your location. "
                            "This is a geolocation restriction by Binance. "
                            "Solutions: 1) Use a VPN to connect from an allowed location, "
                            "2) Use testnet mode if available, "
                            "3) Contact Binance support if you believe this is an error."
                        )
                    
                    logger.error(f"Portfolio Margin API error [{error_code}]: {error_msg}")
                    raise Exception(f"Portfolio Margin API error: {error_msg}")
                
                return data
        except Exception as e:
            error_str = str(e)
            if 'ISP blocking' in error_str:
                raise
            logger.error(f"Portfolio Margin request failed: {error_str}, URL: {url}")
            raise
    
    async def get_portfolio_margin_account_info(self) -> Dict:
        """
        Get Portfolio Margin account information
        Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Account-Information
        """
        try:
            return await self._portfolio_margin_request("GET", "/papi/v1/account", signed=True, weight=20)
        except Exception as e:
            logger.warning(f"Portfolio Margin account info failed, using spot account: {e}")
            # Fallback to spot account
            return await self.get_account_info()
    
    async def get_portfolio_margin_balance(self, asset: Optional[str] = None) -> Dict:
        """
        Get Portfolio Margin account balance
        Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Account-Balance
        
        Args:
            asset: Optional asset symbol (e.g., 'USDT'). If None, returns all assets.
        """
        params = {}
        if asset:
            params["asset"] = asset
        
        try:
            return await self._portfolio_margin_request("GET", "/papi/v1/balance", params, signed=True, weight=20)
        except Exception as e:
            logger.warning(f"Portfolio Margin balance failed, using spot balance: {e}")
            # Fallback to spot balance
            account = await self.get_account_info()
            balances = account.get('balances', [])
            if asset:
                return next((b for b in balances if b['asset'] == asset), {})
            return balances
    
    async def get_um_account_detail(self) -> Dict:
        """
        Get UM (Unified Margin) Account Detail for Portfolio Margin
        Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Get-UM-Account-Detail
        
        Returns detailed information about assets and positions in the UM account including:
        - Assets: cross wallet balance, unrealized PnL, margin requirements
        - Positions: current positions, leverage, entry prices, unrealized profit
        """
        try:
            return await self._portfolio_margin_request("GET", "/papi/v1/um/account", signed=True, weight=5)
        except Exception as e:
            logger.warning(f"UM account detail failed: {e}")
            # Fallback: return empty structure
            return {
                "assets": [],
                "positions": []
            }
    
    async def get_max_withdraw(self, asset: str) -> Dict:
        """
        Query maximum withdrawable amount for Portfolio Margin
        Reference: https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-Margin-Max-Withdraw
        
        Args:
            asset: Asset symbol (e.g., 'USDT')
        """
        params = {"asset": asset}
        try:
            return await self._portfolio_margin_request("GET", "/papi/v1/margin/maxWithdraw", params, signed=True, weight=5)
        except Exception as e:
            logger.warning(f"Max withdraw query failed: {e}")
            # Fallback: get available balance from spot account
            account = await self.get_account_info()
            balances = account.get('balances', [])
            balance = next((b for b in balances if b['asset'] == asset), None)
            if balance:
                return {"amount": balance.get('free', '0')}
            return {"amount": "0"}
    
    async def withdraw(
        self,
        asset: str,
        amount: float,
        address: str,
        network: Optional[str] = None,
        address_tag: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict:
        """
        Withdraw funds from account
        Reference: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/withdraw
        
        Args:
            asset: Asset symbol (e.g., 'USDT')
            amount: Amount to withdraw
            address: Destination address
            network: Network (e.g., 'BSC', 'ETH', 'TRX'). If None, uses default network.
            address_tag: Address tag (for some networks like XRP, XLM)
            name: Description/name for the withdrawal
        """
        params = {
            "asset": asset,
            "amount": amount,
            "address": address,
        }
        
        if network:
            params["network"] = network
        if address_tag:
            params["addressTag"] = address_tag
        if name:
            params["name"] = name
        
        # Withdraw uses /sapi/v1/capital/withdraw/apply (Spot API)
        if self.testnet:
            # Testnet doesn't support real withdrawals
            logger.warning("Withdrawal attempted on testnet - returning mock response")
            return {
                "id": "testnet_withdrawal_" + str(int(time.time())),
                "msg": "Testnet withdrawal (not real)"
            }
        
        # Spot API uses https://api.binance.com (without /api suffix for /sapi endpoints)
        withdraw_base_url = "https://api.binance.com" if not self.testnet else self.base_url
        
        # Apply rate limiting
        await self._wait_for_rate_limit(1)
        
        if not self.session:
            await self.initialize()
        
        url = f"{withdraw_base_url}/sapi/v1/capital/withdraw/apply"
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        # Add signature
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generate_signature(params)
        
        # Validate URL
        if 'internet-positif' in url.lower() or 'binance' not in url.lower():
            logger.error(f"⚠️ Invalid Withdrawal URL: {url}")
            raise Exception("Invalid Withdrawal API URL. This might indicate DNS hijacking or ISP blocking.")
        
        try:
            async with self.session.request("POST", url, params=params, headers=headers, timeout=30, allow_redirects=False) as response:
                if response.status in [301, 302, 303, 307, 308]:
                    redirect_url = response.headers.get('Location', '')
                    logger.error(f"⚠️ ISP Blocking in Withdrawal! Redirected to: {redirect_url}")
                    raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type.lower():
                    text = await response.text()
                    if 'internet-positif' in text.lower():
                        logger.error(f"⚠️ ISP Blocking in Withdrawal! URL: {response.url}")
                        raise Exception("ISP blocking detected: Binance is blocked. Please use VPN.")
                    raise Exception(f"Unexpected HTML response from Withdrawal API: {response.url}")
                
                try:
                    data = await response.json()
                except Exception as json_error:
                    text = await response.text()
                    logger.error(f"Failed to parse JSON from Withdrawal. Response: {text[:200]}")
                    raise Exception(f"Invalid JSON response from Withdrawal API.")
                
                if response.status != 200:
                    error_msg = data.get('msg', 'Unknown error')
                    error_code = data.get('code', 'N/A')
                    
                    # Check for restricted location error (geolocation blocking)
                    if 'restricted location' in error_msg.lower() or 'eligibility' in error_msg.lower():
                        # Activate circuit breaker
                        self._geolocation_blocked = True
                        self._geolocation_blocked_until = datetime.now() + timedelta(seconds=self._geolocation_block_duration)
                        logger.error(
                            f"⚠️ Binance geolocation restriction in Withdrawal [{error_code}]: {error_msg}. "
                            f"Circuit breaker activated for {self._geolocation_block_duration}s."
                        )
                        raise Exception(
                            "Binance API is not available in your location. "
                            "This is a geolocation restriction by Binance. "
                            "Solutions: 1) Use a VPN to connect from an allowed location, "
                            "2) Use testnet mode if available, "
                            "3) Contact Binance support if you believe this is an error."
                        )
                    
                    logger.error(f"Withdrawal API error [{error_code}]: {error_msg}")
                    raise Exception(f"Withdrawal API error: {error_msg}")
                
                return data
        except Exception as e:
            error_str = str(e)
            if 'ISP blocking' in error_str:
                raise
            logger.error(f"Withdrawal request failed: {error_str}, URL: {url}")
            raise
