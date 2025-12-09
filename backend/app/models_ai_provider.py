"""
AI Provider Configuration Models
Supports OpenRouter (cloud) and AgentRouter (local CLI)
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Import Base from app.models to maintain consistency
try:
    from app.models import Base
except ImportError:
    # Fallback if app.models not available
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()


class AIProviderConfig(Base):
    """
    AI Provider Configuration per user
    Supports multiple providers with fallback strategy
    """
    __tablename__ = "ai_provider_config"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Active Provider Selection
    active_provider = Column(String(50), nullable=False, default="openrouter")  # 'openrouter' or 'agentrouter'
    
    # OpenRouter Configuration (Cloud-based, simple API key)
    openrouter_enabled = Column(Boolean, default=True)
    openrouter_api_key = Column(String(500), nullable=True)  # Encrypted
    openrouter_model = Column(String(100), default="qwen/qwen3-max")  # qwen/qwen3-max, deepseek-v3, claude-3.5-sonnet
    openrouter_last_status = Column(String(50), nullable=True)  # 'active', 'error', 'no_credits'
    openrouter_last_error = Column(Text, nullable=True)
    openrouter_credits_remaining = Column(Integer, nullable=True)
    
    # AgentRouter Configuration (Local CLI-based)
    agentrouter_enabled = Column(Boolean, default=False)
    agentrouter_api_key = Column(String(500), nullable=True)  # Encrypted
    agentrouter_base_url = Column(String(500), default="http://localhost:3000")  # CLI endpoint
    agentrouter_model = Column(String(100), default="qwen")  # qwen, claude, deepseek-v3.2, gpt-5
    agentrouter_cli_installed = Column(Boolean, default=False)
    agentrouter_cli_version = Column(String(50), nullable=True)
    agentrouter_last_status = Column(String(50), nullable=True)  # 'active', 'error', 'not_installed', 'not_running'
    agentrouter_last_error = Column(Text, nullable=True)
    
    # Fallback Strategy
    auto_fallback = Column(Boolean, default=True)
    fallback_order = Column(Text, default="openrouter,agentrouter")  # Comma-separated priority list
    
    # Statistics & Monitoring
    total_requests = Column(Integer, default=0)
    openrouter_requests = Column(Integer, default=0)
    agentrouter_requests = Column(Integer, default=0)
    fallback_triggered = Column(Integer, default=0)
    last_request_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", backref="ai_provider_config")
    
    def __repr__(self):
        return f"<AIProviderConfig(user_id={self.user_id}, active={self.active_provider})>"
    
    def to_dict(self, include_secrets=False):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "active_provider": self.active_provider,
            "openrouter": {
                "enabled": self.openrouter_enabled,
                "api_key_set": bool(self.openrouter_api_key),
                "api_key_preview": self._mask_api_key(self.openrouter_api_key) if self.openrouter_api_key else None,
                "api_key": self.openrouter_api_key if include_secrets else None,
                "model": self.openrouter_model,
                "status": self.openrouter_last_status,
                "credits_remaining": self.openrouter_credits_remaining,
                "last_error": self.openrouter_last_error,
                "requests_count": self.openrouter_requests
            },
            "agentrouter": {
                "enabled": self.agentrouter_enabled,
                "api_key_set": bool(self.agentrouter_api_key),
                "api_key_preview": self._mask_api_key(self.agentrouter_api_key) if self.agentrouter_api_key else None,
                "api_key": self.agentrouter_api_key if include_secrets else None,
                "base_url": self.agentrouter_base_url,
                "model": self.agentrouter_model,
                "cli_installed": self.agentrouter_cli_installed,
                "cli_version": self.agentrouter_cli_version,
                "status": self.agentrouter_last_status,
                "last_error": self.agentrouter_last_error,
                "requests_count": self.agentrouter_requests
            },
            "auto_fallback": self.auto_fallback,
            "fallback_order": self.fallback_order.split(",") if self.fallback_order else [],
            "statistics": {
                "total_requests": self.total_requests,
                "fallback_triggered": self.fallback_triggered,
                "last_request_at": self.last_request_at.isoformat() if self.last_request_at else None
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """Mask API key for display (show first 8 chars)"""
        if not api_key or len(api_key) < 12:
            return "***"
        return f"{api_key[:8]}...{api_key[-4:]}"
    
    def get_fallback_order_list(self) -> list:
        """Get fallback order as list"""
        return [p.strip() for p in self.fallback_order.split(",") if p.strip()]
    
    def increment_stats(self, provider: str, is_fallback: bool = False):
        """Increment usage statistics"""
        self.total_requests += 1
        self.last_request_at = func.now()
        
        if provider == "openrouter":
            self.openrouter_requests += 1
        elif provider == "agentrouter":
            self.agentrouter_requests += 1
        
        if is_fallback:
            self.fallback_triggered += 1


class AIProviderLog(Base):
    """
    Log AI provider requests for debugging and analytics
    """
    __tablename__ = "ai_provider_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Request Info
    provider = Column(String(50), nullable=False, index=True)  # 'openrouter' or 'agentrouter'
    model = Column(String(100), nullable=False)
    mode = Column(String(50), nullable=False)  # 'scalper', 'normal', etc.
    is_fallback = Column(Boolean, default=False)
    
    # Response Info
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    recommendations_count = Column(Integer, default=0)
    
    # Performance
    latency_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    
    # Cost (for OpenRouter)
    cost_credits = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", backref="ai_provider_logs")
    
    def __repr__(self):
        return f"<AIProviderLog(provider={self.provider}, success={self.success})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "model": self.model,
            "mode": self.mode,
            "is_fallback": self.is_fallback,
            "success": self.success,
            "error_message": self.error_message,
            "recommendations_count": self.recommendations_count,
            "latency_ms": self.latency_ms,
            "cost_credits": self.cost_credits,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

