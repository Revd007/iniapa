"""
Binance API Service
Handles all interactions with Binance API (Testnet and Production)
"""

import aiohttp
import hashlib
import hmac
import time
from typing import Dict, List, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class BinanceService:
    """Service for interacting with Binance API"""
    
    def __init__(self):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.base_url = settings.binance_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def initialize(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession()
        logger.info(f"Binance service initialized (Testnet: {settings.BINANCE_TESTNET})")
        
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            
    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature for authenticated requests"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """Make HTTP request to Binance API"""
        if not self.session:
            await self.initialize()
            
        url = f"{self.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
        
        if params is None:
            params = {}
            
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
            
        try:
            async with self.session.request(method, url, params=params, headers=headers) as response:
                data = await response.json()
                if response.status != 200:
                    logger.error(f"Binance API error: {data}")
                    raise Exception(f"Binance API error: {data}")
                return data
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    async def get_ticker_price(self, symbol: str) -> Dict:
        """Get current ticker price for a symbol"""
        try:
            data = await self._request("GET", "/v3/ticker/price", {"symbol": symbol})
            return data
        except Exception as e:
            logger.error(f"Failed to get ticker price for {symbol}: {str(e)}")
            # Return mock data for demo
            return {"symbol": symbol, "price": "0"}
    
    async def get_24h_ticker(self, symbol: str) -> Dict:
        """Get 24-hour ticker statistics"""
        try:
            data = await self._request("GET", "/v3/ticker/24hr", {"symbol": symbol})
            return data
        except Exception as e:
            logger.error(f"Failed to get 24h ticker for {symbol}: {str(e)}")
            # Return mock data for demo
            return {
                "symbol": symbol,
                "priceChange": "0",
                "priceChangePercent": "0",
                "lastPrice": "0",
                "volume": "0",
                "quoteVolume": "0"
            }
    
    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List:
        """Get candlestick/kline data"""
        try:
            data = await self._request("GET", "/v3/klines", {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            })
            return data
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {str(e)}")
            return []
    
    async def get_order_book(self, symbol: str, limit: int = 10) -> Dict:
        """Get order book depth"""
        try:
            data = await self._request("GET", "/v3/depth", {
                "symbol": symbol,
                "limit": limit
            })
            return data
        except Exception as e:
            logger.error(f"Failed to get order book for {symbol}: {str(e)}")
            return {"bids": [], "asks": []}
    
    async def create_order(self, symbol: str, side: str, order_type: str, 
                          quantity: float, price: Optional[float] = None,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None) -> Dict:
        """Create a new order with optional SL/TP (requires authentication)"""
        params = {
            "symbol": symbol,
            "side": side,  # BUY or SELL
            "type": order_type,  # MARKET, LIMIT, etc.
            "quantity": quantity
        }
        
        if order_type == "LIMIT" and price:
            params["price"] = price
            params["timeInForce"] = "GTC"
        
        try:
            # Create main order
            data = await self._request("POST", "/v3/order", params, signed=True)
            logger.info(f"Order created: {data}")
            
            # Create Stop Loss order if provided
            if stop_loss and data.get("status") == "FILLED":
                sl_side = "SELL" if side == "BUY" else "BUY"
                sl_params = {
                    "symbol": symbol,
                    "side": sl_side,
                    "type": "STOP_LOSS_LIMIT",
                    "quantity": quantity,
                    "stopPrice": stop_loss,
                    "price": stop_loss,
                    "timeInForce": "GTC"
                }
                try:
                    sl_order = await self._request("POST", "/v3/order", sl_params, signed=True)
                    data["stop_loss_order"] = sl_order
                    logger.info(f"Stop Loss order created: {sl_order}")
                except Exception as e:
                    logger.error(f"Failed to create stop loss: {str(e)}")
            
            # Create Take Profit order if provided
            if take_profit and data.get("status") == "FILLED":
                tp_side = "SELL" if side == "BUY" else "BUY"
                tp_params = {
                    "symbol": symbol,
                    "side": tp_side,
                    "type": "TAKE_PROFIT_LIMIT",
                    "quantity": quantity,
                    "stopPrice": take_profit,
                    "price": take_profit,
                    "timeInForce": "GTC"
                }
                try:
                    tp_order = await self._request("POST", "/v3/order", tp_params, signed=True)
                    data["take_profit_order"] = tp_order
                    logger.info(f"Take Profit order created: {tp_order}")
                except Exception as e:
                    logger.error(f"Failed to create take profit: {str(e)}")
            
            return data
        except Exception as e:
            logger.error(f"Failed to create order: {str(e)}")
            raise
    
    async def get_account_info(self) -> Dict:
        """Get account information (requires authentication)"""
        try:
            data = await self._request("GET", "/v3/account", signed=True)
            return data
        except Exception as e:
            logger.error(f"Failed to get account info: {str(e)}")
            return {"balances": []}
    
    async def get_market_overview(self, symbols: List[str]) -> List[Dict]:
        """Get market overview for multiple symbols"""
        overview = []
        
        for symbol in symbols:
            try:
                ticker = await self.get_24h_ticker(symbol)
                
                # Format for frontend
                overview.append({
                    "symbol": symbol.replace("USDT", "/USD"),
                    "price": f"{float(ticker.get('lastPrice', 0)):.2f}",
                    "change": f"{float(ticker.get('priceChangePercent', 0)):.2f}%",
                    "volume": f"{float(ticker.get('volume', 0)) / 1000000:.1f}M",
                    "high24h": ticker.get('highPrice', '0'),
                    "low24h": ticker.get('lowPrice', '0'),
                    "raw_price": float(ticker.get('lastPrice', 0)),
                    "raw_change": float(ticker.get('priceChangePercent', 0))
                })
            except Exception as e:
                logger.error(f"Failed to get overview for {symbol}: {str(e)}")
                
        return overview
    
    async def get_chart_data(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """Get formatted chart data"""
        klines = await self.get_klines(symbol, interval, limit)
        
        chart_data = []
        for kline in klines:
            try:
                chart_data.append({
                    "time": int(kline[0]),
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "volume": float(kline[5]),
                    "timestamp": kline[0]
                })
            except Exception as e:
                logger.error(f"Failed to parse kline data: {str(e)}")
                
        return chart_data
    
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

