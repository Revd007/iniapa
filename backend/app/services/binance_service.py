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
    
    async def initialize(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession()
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
        # Apply rate limiting before making request
        await self._wait_for_rate_limit(weight)
        
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            async with self.session.request(method, url, params=params, headers=headers, timeout=30) as response:
                data = await response.json()
                
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
                    logger.error(f"Binance API error [{error_code}]: {error_msg}")
                    raise Exception(f"Binance API error: {error_msg}")
                
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
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
        """Get account information"""
        return await self._request("GET", "/v3/account", signed=True)
