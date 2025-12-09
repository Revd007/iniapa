"""
Unified AI Provider Service
Manages OpenRouter (cloud) and AgentRouter (local CLI) with automatic fallback
"""

import aiohttp
import json
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models_ai_provider import AIProviderConfig, AIProviderLog
from app.database import get_db_context

logger = logging.getLogger(__name__)


class BaseAIProvider:
    """Base class for AI providers"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def is_enabled(self) -> bool:
        """Check if provider is enabled and configured"""
        raise NotImplementedError
    
    async def generate(self, prompt: str, mode: str, **kwargs) -> List[Dict]:
        """Generate AI recommendations"""
        raise NotImplementedError
    
    async def test_connection(self) -> Dict:
        """Test provider connection and return status"""
        raise NotImplementedError
    
    def get_name(self) -> str:
        """Get provider name"""
        raise NotImplementedError


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter cloud-based AI provider"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = config.get("model", "qwen/qwen3-max")
        self.enabled = config.get("enabled", True)
    
    def get_name(self) -> str:
        return "openrouter"
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_key)
    
    async def test_connection(self) -> Dict:
        """Test OpenRouter connection"""
        if not self.api_key:
            return {
                "success": False,
                "status": "error",
                "message": "API key not configured"
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple test request
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10
            }
            
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "status": "active",
                            "message": "Connection successful",
                            "details": {
                                "latency_ms": latency_ms,
                                "model": self.model
                            }
                        }
                    elif response.status == 402:
                        return {
                            "success": False,
                            "status": "no_credits",
                            "message": "Insufficient credits",
                            "details": {
                                "latency_ms": latency_ms
                            }
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "status": "error",
                            "message": f"HTTP {response.status}: {error_text[:200]}"
                        }
        
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Connection failed: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }
    
    async def generate(self, prompt: str, mode: str, **kwargs) -> List[Dict]:
        """Generate recommendations using OpenRouter"""
        import aiohttp
        import json
        import time
        
        if not self.api_key:
            raise Exception("OpenRouter API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tradanalisa.app",
            "X-Title": "NOF1 Trading Bot"
        }
        
        payload = {
            "model": self.model,
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
        
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"OpenRouter error: HTTP {response.status} - {error_text[:200]}")
                    
                    data = await response.json()
                    
                    if 'choices' not in data or len(data['choices']) == 0:
                        raise Exception("OpenRouter response missing choices")
                    
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
                    
                    # Basic validation
                    validated = []
                    for rec in recommendations:
                        if all(key in rec for key in ['symbol', 'signal', 'confidence', 'reason']):
                            validated.append(rec)
                    
                    return validated
        except Exception as e:
            raise Exception(f"OpenRouter generation failed: {str(e)}")


class AgentRouterProvider(BaseAIProvider):
    """AgentRouter local CLI-based AI provider"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "http://localhost:3000")
        self.model = config.get("model", "qwen")
        self.enabled = config.get("enabled", False)
        self.cli_installed = config.get("cli_installed", False)
    
    def get_name(self) -> str:
        return "agentrouter"
    
    def is_enabled(self) -> bool:
        return (
            self.enabled and 
            bool(self.api_key) and 
            self.cli_installed
        )
    
    async def check_cli_status(self) -> Dict:
        """Check if Qwen CLI is installed and running"""
        try:
            async with aiohttp.ClientSession() as session:
                # Try to connect to CLI health endpoint
                async with session.get(
                    f"{self.base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "installed": True,
                            "running": True,
                            "version": data.get("version", "unknown"),
                            "base_url": self.base_url
                        }
        except aiohttp.ClientConnectorError:
            # CLI not running
            return {
                "installed": None,  # Can't determine if not running
                "running": False,
                "version": None,
                "base_url": self.base_url,
                "message": "CLI not responding. Make sure it's running: agentrouter start --port 3000"
            }
        except Exception as e:
            return {
                "installed": False,
                "running": False,
                "version": None,
                "error": str(e)
            }
    
    async def test_connection(self) -> Dict:
        """Test AgentRouter connection"""
        if not self.api_key:
            return {
                "success": False,
                "status": "error",
                "message": "API key not configured"
            }
        
        # First check CLI status
        cli_status = await self.check_cli_status()
        
        if not cli_status["running"]:
            return {
                "success": False,
                "status": "not_running",
                "message": cli_status.get("message", "Qwen CLI is not running"),
                "details": cli_status
            }
        
        # Test API call
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 10
            }
            
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "status": "active",
                            "message": "Connection successful",
                            "details": {
                                "latency_ms": latency_ms,
                                "cli_version": cli_status.get("version"),
                                "model": self.model,
                                "base_url": self.base_url
                            }
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "status": "error",
                            "message": f"HTTP {response.status}: {error_text[:200]}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Request failed: {str(e)}"
            }
    
    async def generate(self, prompt: str, mode: str, **kwargs) -> List[Dict]:
        """Generate recommendations using AgentRouter (Qwen CLI)"""
        import aiohttp
        import json
        
        # Check CLI status first
        cli_status = await self.check_cli_status()
        if not cli_status["running"]:
            raise Exception("Qwen CLI not running")
        
        if not self.api_key:
            raise Exception("AgentRouter API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
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
        
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            # AgentRouter/Qwen CLI uses /v1/chat/completions endpoint
            endpoint = f"{self.base_url}/v1/chat/completions"
            async with aiohttp.ClientSession() as session:
                    async with session.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=timeout
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"AgentRouter error: HTTP {response.status} - {error_text[:200]}")
                        
                        data = await response.json()
                        
                        if 'choices' not in data or len(data['choices']) == 0:
                            raise Exception("AgentRouter response missing choices")
                        
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
                        
                        # Basic validation
                        validated = []
                        for rec in recommendations:
                            if all(key in rec for key in ['symbol', 'signal', 'confidence', 'reason']):
                                validated.append(rec)
                        
                        return validated
        except Exception as e:
            raise Exception(f"AgentRouter generation failed: {str(e)}")


class AIProviderManager:
    """
    Manages multiple AI providers with automatic fallback
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.config = self._load_config()
        self.providers = self._initialize_providers()
    
    def _load_config(self) -> AIProviderConfig:
        """Load user's AI provider configuration from database"""
        with get_db_context() as db:
            config = db.query(AIProviderConfig).filter_by(user_id=self.user_id).first()
            
            if not config:
                # Create default config
                config = AIProviderConfig(
                    user_id=self.user_id,
                    active_provider="openrouter",
                    openrouter_enabled=True,
                    agentrouter_enabled=False,
                    auto_fallback=True,
                    fallback_order="openrouter,agentrouter"
                )
                db.add(config)
                db.commit()
                db.refresh(config)
                logger.info(f"Created default AI provider config for user {self.user_id}")
            
            # Extract all needed attributes to avoid session issues
            # Create a new object with all attributes copied
            config_dict = {
                'id': config.id,
                'user_id': config.user_id,
                'active_provider': config.active_provider,
                'openrouter_enabled': config.openrouter_enabled,
                'openrouter_api_key': config.openrouter_api_key,
                'openrouter_model': config.openrouter_model,
                'openrouter_credits_remaining': config.openrouter_credits_remaining,
                'agentrouter_enabled': config.agentrouter_enabled,
                'agentrouter_api_key': config.agentrouter_api_key,
                'agentrouter_base_url': config.agentrouter_base_url,
                'agentrouter_model': config.agentrouter_model,
                'agentrouter_cli_installed': config.agentrouter_cli_installed,
                'auto_fallback': config.auto_fallback,
                'fallback_order': config.fallback_order,
                'total_requests': config.total_requests,
                'fallback_triggered': config.fallback_triggered,
                'last_request_at': config.last_request_at,
            }
            
            # Create a simple object to hold config data
            class ConfigHolder:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
                
                def get_fallback_order_list(self):
                    return [p.strip() for p in self.fallback_order.split(',') if p.strip()]
            
            return ConfigHolder(config_dict)
    
    def _initialize_providers(self) -> Dict[str, BaseAIProvider]:
        """Initialize provider instances"""
        return {
            "openrouter": OpenRouterProvider({
                "enabled": self.config.openrouter_enabled,
                "api_key": self.config.openrouter_api_key,
                "model": self.config.openrouter_model
            }),
            "agentrouter": AgentRouterProvider({
                "enabled": self.config.agentrouter_enabled,
                "api_key": self.config.agentrouter_api_key,
                "base_url": self.config.agentrouter_base_url,
                "model": self.config.agentrouter_model,
                "cli_installed": self.config.agentrouter_cli_installed
            })
        }
    
    async def generate_recommendations(
        self, 
        mode: str, 
        market_data: List[Dict],
        **kwargs
    ) -> tuple[List[Dict], str]:
        """
        Generate AI recommendations with automatic fallback
        
        Returns:
            (recommendations, provider_used)
        """
        start_time = time.time()
        active_provider_name = self.config.active_provider
        
        logger.info(f"🤖 Generating recommendations using: {active_provider_name}")
        
        # Try active provider first
        try:
            provider = self.providers[active_provider_name]
            
            if not provider.is_enabled():
                logger.warning(f"⚠️ {active_provider_name} is not enabled or configured")
                raise Exception(f"{active_provider_name} is not properly configured")
            
            # Generate recommendations
            prompt = self._create_prompt(mode, market_data, **kwargs)
            result = await provider.generate(prompt, mode, **kwargs)
            
            if result:
                latency_ms = int((time.time() - start_time) * 1000)
                self._log_request(active_provider_name, True, len(result), latency_ms, False)
                logger.info(f"✅ {active_provider_name} success ({len(result)} recommendations, {latency_ms}ms)")
                return result, active_provider_name
        
        except Exception as e:
            logger.error(f"❌ {active_provider_name} failed: {str(e)}")
            self._log_request(active_provider_name, False, 0, 0, False, str(e))
            
            # Try fallback if enabled
            if self.config.auto_fallback:
                fallback_result = await self._try_fallback(mode, market_data, **kwargs)
                if fallback_result:
                    return fallback_result
        
        # All failed
        logger.warning("⚠️ All AI providers failed, using fallback data")
        return [], "fallback"
    
    async def _try_fallback(self, mode, market_data, **kwargs) -> Optional[tuple]:
        """Try providers in fallback order"""
        fallback_order = self.config.get_fallback_order_list()
        
        for provider_name in fallback_order:
            if provider_name == self.config.active_provider:
                continue  # Already tried
            
            logger.warning(f"🔄 Trying fallback provider: {provider_name}")
            
            try:
                provider = self.providers.get(provider_name)
                if not provider or not provider.is_enabled():
                    logger.warning(f"⚠️ {provider_name} not available")
                    continue
                
                start_time = time.time()
                prompt = self._create_prompt(mode, market_data, **kwargs)
                result = await provider.generate(prompt, mode, asset_class=kwargs.get('asset_class', 'crypto'), **kwargs)
                
                if result:
                    latency_ms = int((time.time() - start_time) * 1000)
                    self._log_request(provider_name, True, len(result), latency_ms, True)
                    logger.info(f"✅ Fallback {provider_name} success!")
                    return result, provider_name
            
            except Exception as e:
                logger.error(f"❌ Fallback {provider_name} failed: {str(e)}")
                self._log_request(provider_name, False, 0, 0, True, str(e))
                continue
        
        return None
    
    def _create_prompt(self, mode: str, market_data: List[Dict], **kwargs) -> str:
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
        asset_class = kwargs.get('asset_class', 'crypto')
        tech_context = kwargs.get('tech_context', '')
        history_context = kwargs.get('history_context', '')
        limit = kwargs.get('limit', 6)
        
        # Format market data as string
        market_context_lines = []
        for item in market_data:
            symbol = item.get('symbol', 'UNKNOWN')
            price = item.get('price', '0')
            change = item.get('change', '0')
            volume = item.get('volume', '0')
            high24h = item.get('high24h', '0')
            low24h = item.get('low24h', '0')
            market_context_lines.append(
                f"{symbol}: Price ${price} ({change}%), 24h Range: ${low24h}-${high24h}, Volume: ${volume}"
            )
        market_context = "\n".join(market_context_lines) if market_context_lines else "No market data available"
        
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

3. ENTRY/TARGET/STOP LOSS (MUST BE CLEAR AND SPECIFIC):
   - Entry: Current price ± 0.5% (format: "$XX,XXX.XX" or "$X.XXXX" for small prices)
   - Target: Calculate specific price based on mode:
     * Scalper/Aggressive: 3% profit (BUY: entry * 1.03, SELL: entry * 0.97)
     * Normal: 8% profit (BUY: entry * 1.08, SELL: entry * 0.92)
     * Longhold: 15% profit (BUY: entry * 1.15, SELL: entry * 0.85)
   - Stop Loss: Calculate specific price:
     * Scalper/Aggressive: 2% risk (BUY: entry * 0.98, SELL: entry * 1.02)
     * Normal: 3% risk (BUY: entry * 0.97, SELL: entry * 1.03)
     * Longhold: 5% risk (BUY: entry * 0.95, SELL: entry * 1.05)
   - Format: "$XX,XXX.XX" for prices >= $1000, "$XX.XX" for prices >= $1, "$X.XXXX" for prices < $1
   - NEVER use vague terms like "Market dependent" or "Set 2-5% below entry"
   - ALWAYS provide exact calculated prices

4. REASON FORMAT (MUST BE CLEAR AND INFORMATIVE):
   - Include: Key indicators with actual values, entry price, target price, stop loss
   - Format: "RSI 32 (oversold), MACD bullish cross +12. Price: $95,000. Entry: $95,200, Target: $102,816 (+8%), Stop: $92,344 (-3%)"
   - Max 150 characters
   - Be specific: use actual values, not vague terms

5. QUALITY OVER QUANTITY:
   - Only recommend symbols with STRONG signals (confidence >= 65%)
   - If less than {limit} strong signals, return fewer recommendations
   - Better to return 3 high-quality recommendations than 6 weak ones

6. RESPONSE FORMAT:
   - MUST return valid JSON array
   - NO markdown code blocks (no ```json or ```)
   - NO explanatory text before/after JSON
   - Start with [ and end with ]

Now analyze the market data and provide your {limit} best recommendations in the exact JSON format above."""
        
        return prompt
    
    def _log_request(
        self, 
        provider: str, 
        success: bool, 
        recommendations_count: int,
        latency_ms: int,
        is_fallback: bool,
        error_message: str = None
    ):
        """Log AI provider request"""
        try:
            with get_db_context() as db:
                # Create log entry
                log_entry = AIProviderLog(
                    user_id=self.user_id,
                    provider=provider,
                    model=self.providers[provider].config.get("model", "unknown"),
                    mode="unknown",  # Will be passed from kwargs
                    is_fallback=is_fallback,
                    success=success,
                    error_message=error_message,
                    recommendations_count=recommendations_count,
                    latency_ms=latency_ms
                )
                db.add(log_entry)
                
                # Update statistics
                config = db.query(AIProviderConfig).filter_by(user_id=self.user_id).first()
                if config:
                    config.total_requests += 1
                    if is_fallback:
                        config.fallback_triggered += 1
                    config.last_request_at = datetime.now()
                
                db.commit()
        
        except Exception as e:
            logger.error(f"Failed to log AI provider request: {str(e)}")
    
    async def test_provider(self, provider_name: str) -> Dict:
        """Test specific provider"""
        provider = self.providers.get(provider_name)
        if not provider:
            return {
                "success": False,
                "message": f"Provider '{provider_name}' not found"
            }
        
        return await provider.test_connection()
    
    async def check_agentrouter_cli(self) -> Dict:
        """Check Qwen CLI status"""
        provider = self.providers.get("agentrouter")
        if isinstance(provider, AgentRouterProvider):
            return await provider.check_cli_status()
        return {"installed": False, "running": False}

