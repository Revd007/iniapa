"""
AI Trading Recommendations Service
Uses OpenRouter DeepSeek API for generating trading recommendations
"""

import aiohttp
import json
import logging
from typing import Dict, List
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


class AIRecommendationService:
    """Service for generating AI-powered trading recommendations"""
    
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        
        # Support multiple AI models
        self.model_deepseek = settings.OPENROUTER_MODEL_DEEPSEEK
        self.model_qwen = settings.OPENROUTER_MODEL_QWEN
        
        # Circuit breaker: track consecutive failures per model
        self.circuit_breaker_state = {
            'deepseek': {'failures': 0, 'last_failure': None},
            'qwen': {'failures': 0, 'last_failure': None}
        }
        self.circuit_breaker_threshold = 3  # After 3 failures, wait before retrying
        self.circuit_breaker_cooldown = 300  # 5 minutes cooldown
        
        # Log API key status (without exposing the actual key)
        if self.api_key:
            logger.info(f"OpenRouter API key configured (length: {len(self.api_key)}, starts with: {self.api_key[:10]}...)")
            logger.info(f"AI Models: DeepSeek={self.model_deepseek}, Qwen={self.model_qwen}")
        else:
            logger.warning("OpenRouter API key not configured - AI recommendations will use fallback data")
        
    async def generate_recommendations(
        self,
        mode: str,
        market_data: List[Dict],
        asset_class: str = "crypto",
        technical_data: Dict = None,
        limit: int = 6,
        history_context: str | None = None,
        ai_model: str = "deepseek",  # 'deepseek' or 'qwen'
    ) -> List[Dict]:
        """Generate trading recommendations based on mode, market data, technical indicators and historical context
        
        Args:
            ai_model: Which AI model to use - 'deepseek' (fast, technical) or 'qwen' (advanced reasoning)
        """
        
        # Prepare market context
        market_context = self._format_market_data(market_data)
        
        # Add technical indicators context if available
        tech_context = ""
        if technical_data:
            tech_context = self._format_technical_data(technical_data)
        
        # Create prompt based on trading mode
        prompt = self._create_prompt(
            mode=mode,
            market_context=market_context,
            asset_class=asset_class,
            tech_context=tech_context,
            history_context=history_context or "",
            limit=limit,
        )
        
        # Call AI API (DeepSeek or Qwen)
        try:
            recommendations = await self._call_ai_model(prompt, mode, ai_model)
            
            # If AI call returned empty (circuit breaker, timeout, etc.), use fallback
            if not recommendations:
                logger.warning(f"⚠️ AI recommendations unavailable ({ai_model.upper()}) - using fallback data. DO NOT rely on these for trading decisions!")
                fallback = self._get_fallback_recommendations(mode, market_data)
                # Mark all fallback recommendations with warning
                for rec in fallback:
                    rec['is_fallback'] = True
                    rec['ai_model'] = ai_model
                    rec['warning'] = f"⚠️ {ai_model.upper()} AI unavailable - basic technical analysis only. Not AI-generated."
                return fallback
            
            # Mark AI-generated recommendations
            for rec in recommendations:
                rec['is_fallback'] = False
                rec['ai_model'] = ai_model
                rec['warning'] = None
            
            return recommendations
        except Exception as e:
            logger.error(f"Failed to generate AI recommendations: {str(e)}")
            # Return fallback recommendations with clear warning
            logger.warning("⚠️ CRITICAL: Using fallback recommendations - AI service failed. These are NOT AI-generated!")
            fallback = self._get_fallback_recommendations(mode, market_data)
            for rec in fallback:
                rec['is_fallback'] = True
                rec['warning'] = "⚠️ AI unavailable - basic technical analysis only. Not AI-generated."
            return fallback
    
    def _format_technical_data(self, technical_data: Dict) -> str:
        """Format technical indicators for AI prompt"""
        formatted = []
        for symbol, indicators in technical_data.items():
            parts = [f"\n{symbol} Technical Indicators:"]
            if 'rsi' in indicators:
                parts.append(f"  RSI(14): {indicators['rsi']:.2f}")
            if 'macd' in indicators:
                parts.append(f"  MACD: {indicators['macd']:.2f}")
            if 'macd_signal' in indicators:
                parts.append(f"  MACD Signal: {indicators['macd_signal']:.2f}")
            if 'macd_histogram' in indicators:
                parts.append(f"  MACD Histogram: {indicators['macd_histogram']:.2f}")
            if 'ma20' in indicators:
                parts.append(f"  MA(20): ${indicators['ma20']:.2f}")
            if 'ma50' in indicators:
                parts.append(f"  MA(50): ${indicators['ma50']:.2f}")
            formatted.append("\n".join(parts))
        return "\n".join(formatted)
    
    def _format_market_data(self, market_data: List[Dict]) -> str:
        """Format market data for AI prompt"""
        formatted = []
        for data in market_data:
            formatted.append(
                f"- {data['symbol']}: ${data['price']} ({data['change']}) Volume: {data['volume']}, "
                f"24h High: ${data.get('high24h', 'N/A')}, 24h Low: ${data.get('low24h', 'N/A')}"
            )
        return "\n".join(formatted)
    
    def _create_prompt(
        self,
        mode: str,
        market_context: str,
        asset_class: str,
        tech_context: str = "",
        history_context: str = "",
        limit: int = 6,
    ) -> str:
        """Create AI prompt based on trading mode with technical indicators and historical context"""
        
        mode_descriptions = {
            "scalper": {
                "timeframe": "1-5 minutes",
                "risk": "Very High",
                "leverage": "5-10x",
                "strategy": "Quick in-and-out trades, capitalize on small price movements, high frequency trading"
            },
            "normal": {
                "timeframe": "30min-4H",
                "risk": "Medium to High",
                "leverage": "1-5x",
                "strategy": "Balanced approach, technical analysis with trend following, swing trading"
            },
            "aggressive": {
                "timeframe": "15min-1H",
                "risk": "Very High",
                "leverage": "5-15x",
                "strategy": "High-risk high-reward, breakout trading, momentum plays"
            },
            "longhold": {
                "timeframe": "Daily to Monthly",
                "risk": "Low to Medium",
                "leverage": "1-2x",
                "strategy": "Long-term investment, fundamental analysis, position trading"
            }
        }
        
        mode_info = mode_descriptions.get(mode, mode_descriptions["normal"])
        
        prompt = f"""You are a professional cryptocurrency trading analyst with 10+ years of experience in technical analysis and risk management. Your recommendations have an 80%+ win rate.

CRITICAL: Your analysis will be used for REAL MONEY trading. Be accurate, conservative, and data-driven. DO NOT make random or speculative recommendations.

Trading Mode: {mode.upper()}
- Timeframe: {mode_info['timeframe']}
- Risk Level: {mode_info['risk']}
- Recommended Leverage: {mode_info['leverage']}
- Strategy Focus: {mode_info['strategy']}

=== CURRENT MARKET DATA ===
{market_context}

=== TECHNICAL INDICATORS (Real-time from chart data) ===
{tech_context if tech_context else "⚠️ No technical indicator data available - analysis may be less accurate"}

=== HISTORICAL PERFORMANCE (Your past recommendations) ===
{history_context if history_context else "No trade history yet. This is a fresh start - make your best recommendation based on current data."}

=== TECHNICAL ANALYSIS RULES (Follow these strictly) ===

RSI (14-period):
- RSI > 70: OVERBOUGHT → Bearish signal, avoid BUY, consider SELL
- RSI 50-70: Bullish momentum → BUY if other indicators confirm
- RSI 30-50: Neutral to Bearish → HOLD or wait for confirmation
- RSI < 30: OVERSOLD → Bullish signal, strong BUY opportunity

MACD (12, 26, 9):
- MACD Line > Signal Line AND Histogram growing: STRONG BULLISH → BUY
- MACD Line < Signal Line AND Histogram shrinking: STRONG BEARISH → SELL
- MACD Line crossing above Signal: Bullish crossover → BUY
- MACD Line crossing below Signal: Bearish crossover → SELL

Moving Averages (MA20, MA50):
- Price > MA20 > MA50: STRONG UPTREND → BUY
- Price < MA20 < MA50: STRONG DOWNTREND → SELL
- MA20 > MA50 (Golden Cross): Bullish → BUY
- MA20 < MA50 (Death Cross): Bearish → SELL
- Price between MA20 and MA50: CONSOLIDATION → HOLD

Volume Analysis:
- High volume + price up: Strong uptrend → BUY
- High volume + price down: Strong downtrend → SELL
- Low volume: Weak signal → reduce confidence

Multi-Indicator Confirmation (CRITICAL):
- Only give STRONG BUY/SELL when at least 3 indicators align
- If indicators conflict, use HOLD or reduce confidence
- Always check price action vs moving averages for trend confirmation

=== OUTPUT FORMAT (STRICT JSON) ===

Provide exactly {limit} recommendations in this JSON format:
[
  {{
    "symbol": "BTC",
    "name": "Bitcoin",
    "signal": "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL",
    "confidence": 75,
    "reason": "RSI 32 (oversold), MACD bullish cross, price above MA20. Strong buy setup.",
    "riskLevel": "Low" | "Medium" | "High" | "Very High",
    "timeframe": "{mode_info['timeframe']}",
    "leverage": "{mode_info['leverage']}",
    "entry_price": "$95,000 - $95,500",
    "target_price": "$98,000",
    "stop_loss": "$93,500"
  }}
]

=== CRITICAL REQUIREMENTS ===

1. CONFIDENCE RULES:
   - 85-95%: All 3+ indicators strongly align (RSI, MACD, MA trend)
   - 75-84%: 2-3 indicators align, good setup
   - 65-74%: Mixed signals, but one strong indicator
   - Below 65%: Don't recommend, use HOLD instead

2. SIGNAL RULES:
   - STRONG BUY: RSI < 35, MACD bullish cross, Price > MA20, High volume
   - BUY: RSI < 50, MACD > Signal OR Price > MA20
   - HOLD: Indicators conflict, or consolidation phase
   - SELL: RSI > 50, MACD < Signal OR Price < MA20
   - STRONG SELL: RSI > 65, MACD bearish cross, Price < MA20, High volume

3. ENTRY/TARGET/STOP LOSS:
   - Entry: Current price ± 0.5% (tight range)
   - Target: 2-5% profit for scalper/aggressive, 5-15% for normal/longhold
   - Stop Loss: 2-3% below entry for BUY, 2-3% above entry for SELL
   - NEVER set stop loss that risks more than 5%

4. REASON FORMAT:
   - Start with KEY indicators: "RSI 28 (oversold), MACD bullish..."
   - Max 100 characters
   - Be specific: use actual values, not vague terms
   - Examples:
     ✅ "RSI 32 oversold, MACD cross +12, MA20>MA50 uptrend"
     ❌ "Good momentum, looks bullish"

5. QUALITY OVER QUANTITY:
   - Only recommend if confidence >= 65%
   - If you can't find {limit} good setups, recommend fewer with HOLD for others
   - Don't force recommendations on weak setups

6. RISK LEVEL ALIGNMENT:
   - Scalper mode: Most should be "High" or "Very High"
   - Normal mode: Mix of "Medium" and "High"
   - Long hold: Most should be "Low" or "Medium"
   - Aggressive mode: "Very High" is acceptable

Return ONLY the JSON array, no markdown, no explanation, no additional text."""

        return prompt
    
    async def _call_ai_model(self, prompt: str, mode: str, ai_model: str = "deepseek") -> List[Dict]:
        """
        Call OpenRouter AI API (DeepSeek or Qwen) with retry logic and circuit breaker.
        CRITICAL: This function must be reliable - users make trading decisions based on this.
        
        Args:
            ai_model: 'deepseek' or 'qwen'
        """
        import time
        import asyncio
        
        if not self.api_key:
            logger.warning(f"OpenRouter API key not configured, using fallback recommendations")
            return []
        
        # Get model name and circuit breaker state
        model_name = self.model_deepseek if ai_model == "deepseek" else self.model_qwen
        breaker_state = self.circuit_breaker_state.get(ai_model, {'failures': 0, 'last_failure': None})
        
        # Circuit breaker: check if we should skip API call due to recent failures
        if breaker_state['failures'] >= self.circuit_breaker_threshold:
            if breaker_state['last_failure']:
                time_since_failure = time.time() - breaker_state['last_failure']
                if time_since_failure < self.circuit_breaker_cooldown:
                    remaining = int(self.circuit_breaker_cooldown - time_since_failure)
                    logger.warning(
                        f"Circuit breaker active for {ai_model.upper()}: {breaker_state['failures']} consecutive failures. "
                        f"Waiting {remaining}s before retry. Using fallback recommendations."
                    )
                    return []
                else:
                    # Cooldown expired, reset circuit breaker
                    logger.info(f"Circuit breaker cooldown expired for {ai_model.upper()}, attempting API call again")
                    breaker_state['failures'] = 0
                    breaker_state['last_failure'] = None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nof1beta.app",
            "X-Title": "NOF1 Trading Bot"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert cryptocurrency trading analyst providing data-driven recommendations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # Retry logic: 3 attempts with exponential backoff
        max_retries = 3
        base_timeout = 60  # Increased from 30 to 60 seconds
        retry_delays = [2, 5, 10]  # Wait 2s, 5s, 10s between retries
        
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=base_timeout + (attempt * 10))  # Increase timeout per retry
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=timeout
                    ) as response:
                        if response.status != 200:
                            response_text = await response.text()
                            logger.error(
                                f"OpenRouter API error (attempt {attempt + 1}/{max_retries}): "
                                f"HTTP {response.status} - {response_text[:500]}"
                            )
                            
                            # If 4xx error (client error), don't retry
                            if 400 <= response.status < 500:
                                breaker_state['failures'] += 1
                                breaker_state['last_failure'] = time.time()
                                return []
                            
                            # For 5xx or other errors, retry
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delays[attempt])
                                continue
                            else:
                                breaker_state['failures'] += 1
                                breaker_state['last_failure'] = time.time()
                                return []
                        
                        # Success - reset circuit breaker
                        breaker_state['failures'] = 0
                        breaker_state['last_failure'] = None
                        
                        data = await response.json()
                        
                        # Check if response has expected structure
                        if 'choices' not in data or len(data['choices']) == 0:
                            logger.error(f"{ai_model.upper()} response missing choices: {data}")
                            breaker_state['failures'] += 1
                            breaker_state['last_failure'] = time.time()
                            return []
                        
                        content = data['choices'][0]['message']['content']
                        
                        # Parse JSON response
                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]
                        if content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]
                        content = content.strip()
                        
                        recommendations = json.loads(content)
                        
                        # === VALIDATION & QUALITY CONTROL ===
                        # Filter out low-quality recommendations
                        validated_recommendations = []
                        for rec in recommendations:
                            # Validate required fields
                            if not all(key in rec for key in ['symbol', 'signal', 'confidence', 'reason']):
                                logger.warning(f"Skipping recommendation with missing fields: {rec}")
                                continue
                            
                            # Validate confidence range
                            if not isinstance(rec.get('confidence'), (int, float)) or not (50 <= rec['confidence'] <= 100):
                                logger.warning(f"Invalid confidence {rec.get('confidence')} for {rec.get('symbol')}, skipping")
                                continue
                            
                            # Validate signal
                            valid_signals = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
                            if rec.get('signal') not in valid_signals:
                                logger.warning(f"Invalid signal '{rec.get('signal')}' for {rec.get('symbol')}, skipping")
                                continue
                            
                            # Validate reason (must not be empty or too generic)
                            reason = rec.get('reason', '').strip()
                            if len(reason) < 20:
                                logger.warning(f"Reason too short for {rec.get('symbol')}: '{reason}', skipping")
                                continue
                            
                            # Add color coding based on signal
                            rec['color'] = self._get_color_for_signal(rec['signal'])
                            
                            validated_recommendations.append(rec)
                        
                        if not validated_recommendations:
                            logger.error("All AI recommendations failed validation!")
                            return []
                        
                        logger.info(
                            f"✅ Successfully generated {len(validated_recommendations)} AI recommendations "
                            f"for mode: {mode} ({len(recommendations) - len(validated_recommendations)} filtered out)"
                        )
                        return validated_recommendations
                        
            except asyncio.TimeoutError:
                logger.error(
                    f"OpenRouter API timeout (attempt {attempt + 1}/{max_retries}) - "
                    f"timeout was {timeout.total}s"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                else:
                    breaker_state['failures'] += 1
                    breaker_state['last_failure'] = time.time()
                    logger.error(f"⚠️ CRITICAL: All retry attempts failed for {ai_model.upper()}. AI recommendations unavailable.")
                    return []
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse {ai_model.upper()} response as JSON: {str(e)}")
                logger.error(f"Response content: {content[:200] if 'content' in locals() else 'N/A'}")
                breaker_state['failures'] += 1
                breaker_state['last_failure'] = time.time()
                return []
                
            except aiohttp.ClientError as e:
                logger.error(
                    f"OpenRouter API network error (attempt {attempt + 1}/{max_retries}): "
                    f"{type(e).__name__} - {str(e)}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                else:
                    breaker_state['failures'] += 1
                    breaker_state['last_failure'] = time.time()
                    return []
            
            except KeyError as e:
                logger.error(f"{ai_model.upper()} API response missing expected field: {str(e)}")
                breaker_state['failures'] += 1
                breaker_state['last_failure'] = time.time()
                return []
                
            except Exception as e:
                logger.error(
                    f"OpenRouter API unexpected error (attempt {attempt + 1}/{max_retries}): "
                    f"{type(e).__name__} - {str(e)}"
                )
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                else:
                    breaker_state['failures'] += 1
                    breaker_state['last_failure'] = time.time()
                    return []
        
        # Should never reach here, but just in case
        breaker_state['failures'] += 1
        breaker_state['last_failure'] = time.time()
        return []
    
    def _get_color_for_signal(self, signal: str) -> str:
        """Get color class based on trading signal"""
        signal_upper = signal.upper()
        
        if "STRONG BUY" in signal_upper:
            return "bg-green-900 text-green-200 border-green-800"
        elif "BUY" in signal_upper:
            return "bg-blue-900 text-blue-200 border-blue-800"
        elif "STRONG SELL" in signal_upper:
            return "bg-red-900 text-red-200 border-red-800"
        elif "SELL" in signal_upper:
            return "bg-orange-900 text-orange-200 border-orange-800"
        else:  # HOLD
            return "bg-yellow-900 text-yellow-200 border-yellow-800"
    
    def _get_fallback_recommendations(self, mode: str, market_data: List[Dict]) -> List[Dict]:
        """Get fallback recommendations when AI is unavailable"""
        
        # Use top 3 coins from market data
        top_coins = sorted(market_data, key=lambda x: abs(x.get('raw_change', 0)), reverse=True)[:3]
        
        recommendations = []
        for i, coin in enumerate(top_coins):
            symbol = coin['symbol'].split('/')[0]
            change = coin.get('raw_change', 0)
            
            # Determine signal based on price change
            if change > 2:
                signal = "STRONG BUY"
                confidence = min(90, 75 + int(change))
            elif change > 0:
                signal = "BUY"
                confidence = 70 + int(change * 5)
            elif change > -2:
                signal = "HOLD"
                confidence = 65
            else:
                signal = "SELL"
                confidence = 70
            
            recommendations.append({
                "symbol": symbol,
                "name": self._get_coin_name(symbol),
                "signal": signal,
                "confidence": confidence,
                "reason": f"Technical analysis: {change:+.2f}% 24h change, momentum indicator",
                "riskLevel": self._get_risk_level(mode),
                "color": self._get_color_for_signal(signal),
                "timeframe": self._get_timeframe(mode),
                "leverage": self._get_leverage(mode),
                "entry_price": coin['price'],
                "target_price": "Market dependent",
                "stop_loss": "Set 2-5% below entry"
            })
        
        return recommendations
    
    def _get_coin_name(self, symbol: str) -> str:
        """Get full name for crypto symbol"""
        names = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "BNB": "Binance Coin",
            "XRP": "Ripple"
        }
        return names.get(symbol, symbol)
    
    def _get_risk_level(self, mode: str) -> str:
        """Get risk level for trading mode"""
        risk_map = {
            "scalper": "Very High",
            "normal": "Medium",
            "aggressive": "Very High",
            "longhold": "Low"
        }
        return risk_map.get(mode, "Medium")
    
    def _get_timeframe(self, mode: str) -> str:
        """Get timeframe for trading mode"""
        timeframe_map = {
            "scalper": "1-5min",
            "normal": "1H-4H",
            "aggressive": "15min-1H",
            "longhold": "Daily"
        }
        return timeframe_map.get(mode, "1H")
    
    def _get_leverage(self, mode: str) -> str:
        """Get suggested leverage for trading mode"""
        leverage_map = {
            "scalper": "10x",
            "normal": "3x",
            "aggressive": "10x",
            "longhold": "1x"
        }
        return leverage_map.get(mode, "1x")

