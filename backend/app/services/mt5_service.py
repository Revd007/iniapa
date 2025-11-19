"""
MT5 (MetaTrader 5) Service
Handles all interactions with MetaTrader5 for FOREX trading.
"""

import logging
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class MT5Service:
    """Lightweight wrapper around MetaTrader5 package."""

    def __init__(self) -> None:
        self.enabled = settings.MT5_ENABLED
        self._mt5 = None

    async def initialize(self) -> None:
        """Initialize MT5 connection (demo or live). Fast - returns immediately if disabled."""
        if not self.enabled:
            # Fast path: MT5 disabled, no imports needed
            return

        # Lazy import - only import MetaTrader5 if actually needed
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError:
            logger.error("MetaTrader5 package not installed. MT5 features disabled.")
            self.enabled = False
            return

        self._mt5 = mt5

        # MT5.initialize() can be slow, but only runs if enabled
        if not mt5.initialize():
            logger.error(f"MT5 initialize() failed, error code: {mt5.last_error()}")
            self.enabled = False
            return

        if settings.MT5_ENV == "live":
            login = int(settings.MT5_LIVE_LOGIN or 0)
            password = settings.MT5_LIVE_PASSWORD
            server = settings.MT5_LIVE_SERVER
            env_label = "LIVE"
        else:
            login = int(settings.MT5_DEMO_LOGIN or 0)
            password = settings.MT5_DEMO_PASSWORD
            server = settings.MT5_DEMO_SERVER
            env_label = "DEMO"

        if login and password and server:
            if not mt5.login(login=login, password=password, server=server):
                logger.error(f"MT5 login failed ({env_label}): {mt5.last_error()}")
                self.enabled = False
            else:
                logger.info(f"MT5 logged in ({env_label}) as {login}")
        else:
            logger.warning("MT5 credentials not fully configured; MT5 will run in read-only mode.")

    async def close(self) -> None:
        if self._mt5:
            self._mt5.shutdown()
            logger.info("MT5 connection closed.")

    def _ensure_ready(self) -> bool:
        if not self.enabled or not self._mt5:
            return False
        return True

    async def get_forex_symbols(self) -> List[str]:
        """Return list of FOREX symbols (e.g. 'EURUSD', 'XAUUSD')."""
        if not self._ensure_ready():
            return []

        mt5 = self._mt5
        symbols = mt5.symbols_get()
        result: List[str] = []
        for s in symbols:
            # Basic heuristic: FOREX symbols typically end with 'USD', 'EUR', etc.
            name = s.name
            if s.visible and len(name) in (6, 7) and not name.endswith("."):
                result.append(name)
        return result

    async def get_market_overview(self) -> List[Dict]:
        """Return market overview similar to Binance service for all FOREX symbols."""
        if not self._ensure_ready():
            return []

        mt5 = self._mt5
        overview: List[Dict] = []
        symbols = await self.get_forex_symbols()

        for name in symbols:
            try:
                tick = mt5.symbol_info_tick(name)
                info = mt5.symbol_info(name)
                if tick is None or info is None:
                    continue

                price = tick.bid or tick.ask or tick.last
                # volume / high / low are approximated from symbol properties
                overview.append(
                    {
                        "symbol": name,
                        "price": f"{price:.5f}" if price else "0",
                        "change": "0.00%",
                        "volume": f"{info.volume:.1f}",
                        "high24h": "0",
                        "low24h": "0",
                        "raw_price": float(price or 0),
                        "raw_change": 0.0,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to build MT5 overview for {name}: {e}")

        return overview

    async def get_account_summary(self) -> Optional[Dict]:
        """Return MT5 account summary (balance, equity, margin)."""
        if not self._ensure_ready():
            return None

        mt5 = self._mt5
        try:
            info = mt5.account_info()
            if info is None:
                logger.error(f"MT5 account_info() returned None: {mt5.last_error()}")
                return None

            return {
                "balance": float(info.balance),
                "equity": float(info.equity),
                "margin": float(info.margin),
                "margin_free": float(info.margin_free),
                "profit": float(info.profit),
            }
        except Exception as e:
            logger.error(f"Failed to get MT5 account summary: {e}")
            return None

    async def get_chart_data(self, symbol: str, interval: str = "1H", limit: int = 100) -> List[Dict]:
        """Get OHLC chart data from MT5 for a forex symbol."""
        if not self._ensure_ready():
            return []

        mt5 = self._mt5
        try:
          # Map our intervals to MT5 timeframes
            tf_map = {
                "1m": mt5.TIMEFRAME_M1,
                "5m": mt5.TIMEFRAME_M5,
                "15m": mt5.TIMEFRAME_M15,
                "1h": mt5.TIMEFRAME_H1,
                "4h": mt5.TIMEFRAME_H4,
                "1d": mt5.TIMEFRAME_D1,
            }
            timeframe = tf_map.get(interval, mt5.TIMEFRAME_H1)
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, limit)
            if rates is None:
                return []

            data: List[Dict] = []
            for r in rates:
                data.append(
                    {
                        "time": int(r["time"]) * 1000,
                        "open": float(r["open"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": float(r["tick_volume"]),
                    }
                )
            return data
        except Exception as e:
            logger.error(f"Failed to get MT5 chart data for {symbol}: {e}")
            return []


