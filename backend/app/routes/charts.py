"""
Chart Data Routes
Endpoints for retrieving chart data and technical indicators
"""

from fastapi import APIRouter, HTTPException, Request, Query
from typing import List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/klines/{symbol}")
async def get_klines(
    symbol: str,
    request: Request,
    interval: str = Query("1h", description="Kline interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)"),
    limit: int = Query(100, description="Number of data points", ge=1, le=1000),
    asset_class: str = Query("crypto", description="crypto | forex"),
):
    """Get candlestick/kline data for charting (crypto=Binance, forex=MT5)."""
    try:
        if asset_class == "forex":
            mt5_service = getattr(request.app.state, "mt5_service", None)
            if not mt5_service:
                raise HTTPException(status_code=503, detail="MT5 service not available")
            chart_data = await mt5_service.get_chart_data(symbol, interval.upper(), limit)
        else:
            binance_service = request.app.state.binance_service
            # Ensure symbol has USDT suffix
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"
            # Get chart data
            chart_data = await binance_service.get_chart_data(symbol, interval, limit)
        
        # Calculate moving averages
        if len(chart_data) >= 20:
            chart_data = calculate_moving_averages(chart_data)
        
        return {
            "success": True,
            "symbol": symbol,
            "interval": interval,
            "data": chart_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get klines for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart/{symbol}")
async def get_chart_data(
    symbol: str,
    request: Request,
    interval: str = Query("1h", description="Chart interval"),
    limit: int = Query(100, description="Number of candles", ge=1, le=1000),
    asset_class: str = Query("crypto", description="crypto | forex"),
):
    """Get formatted chart data with indicators (crypto=Binance, forex=MT5). Max 1000 candles per request."""
    try:
        if asset_class == "forex":
            mt5_service = getattr(request.app.state, "mt5_service", None)
            if not mt5_service:
                raise HTTPException(status_code=503, detail="MT5 service not available")
            # MT5 already returns formatted OHLC data
            base_data = await mt5_service.get_chart_data(symbol, interval.upper(), limit)
            chart_data = calculate_indicators(base_data) if len(base_data) >= 50 else base_data

            return {
                "success": True,
                "symbol": symbol,
                "interval": interval,
                "data": chart_data,
            }

        binance_service = request.app.state.binance_service

        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        # Get klines
        klines = await binance_service.get_klines(symbol, interval, limit)
        
        if not klines:
            return {
                "success": True,
                "symbol": symbol,
                "data": []
            }
        
        # Format for chart
        chart_data = []
        for kline in klines:
            close_price = float(kline[4])
            chart_data.append({
                "time": int(kline[0]),
                "price": close_price,
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": close_price,
                "volume": float(kline[5])
            })
        
        # Calculate indicators
        if len(chart_data) >= 50:
            chart_data = calculate_indicators(chart_data)
        
        return {
            "success": True,
            "symbol": symbol,
            "interval": interval,
            "data": chart_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get chart data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_moving_averages(data: List[dict]) -> List[dict]:
    """Calculate MA20 and MA50 for chart data"""
    for i in range(len(data)):
        # MA20
        if i >= 19:
            ma20_sum = sum(d['close'] for d in data[i-19:i+1])
            data[i]['ma20'] = round(ma20_sum / 20, 2)
        
        # MA50
        if i >= 49:
            ma50_sum = sum(d['close'] for d in data[i-49:i+1])
            data[i]['ma50'] = round(ma50_sum / 50, 2)
    
    return data


def calculate_indicators(data: List[dict]) -> List[dict]:
    """
    Calculate technical indicators (MA20, MA50, RSI-14, MACD) dengan metode yang benar.
    Formula mengikuti standar TradingView dan platform trading profesional.
    """
    if len(data) < 50:
        return data
    
    # Calculate moving averages (SMA)
    data = calculate_moving_averages(data)
    
    # === RSI (14 period) - Wilder's Smoothing Method ===
    # Ini adalah metode yang digunakan TradingView dan platform profesional
    if len(data) >= 15:
        # Initial average gain and loss (first 14 periods)
        gains = []
        losses = []
        for i in range(1, 15):
            change = data[i]['close'] - data[i-1]['close']
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        
        # Calculate RSI for period 14 onwards using Wilder's smoothing
        for i in range(14, len(data)):
            change = data[i]['close'] - data[i-1]['close']
            
            if change > 0:
                current_gain = change
                current_loss = 0
            else:
                current_gain = 0
                current_loss = abs(change)
            
            # Wilder's smoothing: (previous_avg * 13 + current) / 14
            avg_gain = (avg_gain * 13 + current_gain) / 14
            avg_loss = (avg_loss * 13 + current_loss) / 14
            
            if avg_loss == 0:
                data[i]['rsi'] = 100.0
            else:
                rs = avg_gain / avg_loss
                data[i]['rsi'] = round(100 - (100 / (1 + rs)), 2)
    
    # === MACD (12, 26, 9) - Standard EMA Method ===
    if len(data) >= 26:
        # Calculate EMA12 and EMA26
        multiplier_12 = 2 / (12 + 1)
        multiplier_26 = 2 / (26 + 1)
        
        # Initialize with SMA
        ema_12_values = [None] * len(data)
        ema_26_values = [None] * len(data)
        
        # Calculate initial SMA
        ema_12_values[11] = sum(d['close'] for d in data[:12]) / 12
        ema_26_values[25] = sum(d['close'] for d in data[:26]) / 26
        
        # Calculate EMA12 from period 12 onwards
        for i in range(12, len(data)):
            if ema_12_values[i-1] is not None:
                ema_12_values[i] = (data[i]['close'] - ema_12_values[i-1]) * multiplier_12 + ema_12_values[i-1]
        
        # Calculate EMA26 from period 26 onwards
        for i in range(26, len(data)):
            if ema_26_values[i-1] is not None:
                ema_26_values[i] = (data[i]['close'] - ema_26_values[i-1]) * multiplier_26 + ema_26_values[i-1]
        
        # Calculate MACD = EMA12 - EMA26
        macd_values = []
        for i in range(26, len(data)):
            if ema_12_values[i] is not None and ema_26_values[i] is not None:
                macd_value = ema_12_values[i] - ema_26_values[i]
                data[i]['macd'] = round(macd_value, 4)
                macd_values.append(macd_value)
            else:
                data[i]['macd'] = 0.0
                macd_values.append(0.0)
        
        # Calculate Signal Line (9-period EMA of MACD)
        if len(macd_values) >= 9:
            multiplier_9 = 2 / (9 + 1)
            # Initial signal = SMA of first 9 MACD values
            signal = sum(macd_values[:9]) / 9
            
            # First signal value at index 26 + 8 = 34
            data[34]['macd_signal'] = round(signal, 4)
            data[34]['macd_histogram'] = round(data[34]['macd'] - signal, 4)
            
            # Calculate subsequent signal values with EMA
            for i in range(35, len(data)):
                if 'macd' in data[i]:
                    signal = (data[i]['macd'] - signal) * multiplier_9 + signal
                    data[i]['macd_signal'] = round(signal, 4)
                    data[i]['macd_histogram'] = round(data[i]['macd'] - signal, 4)
    
    return data


@router.get("/realtime/{symbol}")
async def get_realtime_price(symbol: str, request: Request):
    """Get real-time price for a symbol (crypto only for now)"""
    try:
        binance_service = request.app.state.binance_service
        
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        ticker = await binance_service.get_ticker_price(symbol)
        ticker_24h = await binance_service.get_24h_ticker(symbol)
        
        return {
            "success": True,
            "symbol": symbol,
            "price": float(ticker.get('price', 0)),
            "change_24h": float(ticker_24h.get('priceChangePercent', 0)),
            "volume_24h": float(ticker_24h.get('volume', 0)),
            "high_24h": float(ticker_24h.get('highPrice', 0)),
            "low_24h": float(ticker_24h.get('lowPrice', 0))
        }
        
    except Exception as e:
        logger.error(f"Failed to get realtime price for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

