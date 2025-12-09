"""
AI Provider Configuration API Routes
Manage OpenRouter and AgentRouter settings
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from app.database import get_db
from app.models_ai_provider import AIProviderConfig, AIProviderLog
from app.services.ai_provider_service import AIProviderManager, OpenRouterProvider, AgentRouterProvider

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= Request/Response Models =============

class OpenRouterConfigRequest(BaseModel):
    enabled: bool = True
    api_key: Optional[str] = None
    model: str = Field(default="qwen/qwen3-max", description="OpenRouter model name")


class AgentRouterConfigRequest(BaseModel):
    enabled: bool = False
    api_key: Optional[str] = None
    base_url: str = Field(default="http://localhost:3000", description="Qwen CLI endpoint")
    model: str = Field(default="qwen", description="AgentRouter model name")


class AIProviderConfigRequest(BaseModel):
    active_provider: str = Field(default="openrouter", description="Active provider: openrouter or agentrouter")
    openrouter: Optional[OpenRouterConfigRequest] = None
    agentrouter: Optional[AgentRouterConfigRequest] = None
    auto_fallback: bool = Field(default=True, description="Enable automatic fallback")
    fallback_order: List[str] = Field(default=["openrouter", "agentrouter"], description="Fallback priority order")


class TestProviderRequest(BaseModel):
    provider: str = Field(description="Provider to test: openrouter or agentrouter")
    config: Optional[dict] = Field(default=None, description="Optional config override for testing")


# ============= Endpoints =============

@router.get("/config")
async def get_ai_provider_config(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Get current AI provider configuration
    
    Returns user's AI provider settings including:
    - Active provider
    - OpenRouter configuration
    - AgentRouter configuration
    - Fallback settings
    - Usage statistics
    """
    try:
        config = db.query(AIProviderConfig).filter_by(user_id=user_id).first()
        
        if not config:
            # Create default config
            config = AIProviderConfig(
                user_id=user_id,
                active_provider="openrouter",
                openrouter_enabled=True,
                agentrouter_enabled=False,
                auto_fallback=True,
                fallback_order="openrouter,agentrouter"
            )
            db.add(config)
            db.commit()
            db.refresh(config)
            logger.info(f"Created default AI provider config for user {user_id}")
        
        # Get Qwen CLI status
        agentrouter_cli_status = None
        if config.agentrouter_enabled:
            try:
                manager = AIProviderManager(user_id)
                agentrouter_cli_status = await manager.check_agentrouter_cli()
                
                # Update CLI status in database
                config.agentrouter_cli_installed = agentrouter_cli_status.get("running", False)
                config.agentrouter_cli_version = agentrouter_cli_status.get("version")
                db.commit()
            except Exception as e:
                logger.error(f"Failed to check Qwen CLI: {e}")
        
        return {
            "success": True,
            "config": config.to_dict(),
            "agentrouter_cli_status": agentrouter_cli_status
        }
    
    except Exception as e:
        logger.error(f"Failed to get AI provider config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_ai_provider_config(
    request: AIProviderConfigRequest,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Update AI provider configuration
    
    Allows users to:
    - Switch active provider
    - Update API keys and models
    - Configure fallback strategy
    """
    try:
        config = db.query(AIProviderConfig).filter_by(user_id=user_id).first()
        
        if not config:
            config = AIProviderConfig(user_id=user_id)
            db.add(config)
        
        # Update active provider
        if request.active_provider in ["openrouter", "agentrouter"]:
            config.active_provider = request.active_provider
        
        # Update OpenRouter config
        if request.openrouter:
            config.openrouter_enabled = request.openrouter.enabled
            if request.openrouter.api_key:
                config.openrouter_api_key = request.openrouter.api_key
            config.openrouter_model = request.openrouter.model
        
        # Update AgentRouter config
        if request.agentrouter:
            config.agentrouter_enabled = request.agentrouter.enabled
            if request.agentrouter.api_key:
                config.agentrouter_api_key = request.agentrouter.api_key
            config.agentrouter_base_url = request.agentrouter.base_url
            config.agentrouter_model = request.agentrouter.model
        
        # Update fallback settings
        config.auto_fallback = request.auto_fallback
        config.fallback_order = ",".join(request.fallback_order)
        
        db.commit()
        db.refresh(config)
        
        logger.info(f"✅ Updated AI provider config for user {user_id}")
        
        return {
            "success": True,
            "message": "AI provider configuration updated successfully",
            "config": config.to_dict()
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update AI provider config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_ai_provider(
    request: TestProviderRequest,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Test AI provider connection
    
    Performs a test request to verify:
    - API key validity
    - Network connectivity
    - CLI status (for AgentRouter)
    - Response latency
    """
    try:
        if request.provider not in ["openrouter", "agentrouter"]:
            raise HTTPException(status_code=400, detail="Invalid provider. Must be 'openrouter' or 'agentrouter'")
        
        # Get config
        config = db.query(AIProviderConfig).filter_by(user_id=user_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="AI provider config not found")
        
        # Initialize provider
        if request.provider == "openrouter":
            test_config = request.config or {
                "enabled": config.openrouter_enabled,
                "api_key": config.openrouter_api_key,
                "model": config.openrouter_model
            }
            provider = OpenRouterProvider(test_config)
        else:  # agentrouter
            test_config = request.config or {
                "enabled": config.agentrouter_enabled,
                "api_key": config.agentrouter_api_key,
                "base_url": config.agentrouter_base_url,
                "model": config.agentrouter_model,
                "cli_installed": config.agentrouter_cli_installed
            }
            provider = AgentRouterProvider(test_config)
        
        # Test connection
        result = await provider.test_connection()
        
        # Update status in database
        if request.provider == "openrouter":
            config.openrouter_last_status = result.get("status")
            if not result["success"]:
                config.openrouter_last_error = result.get("message")
        else:
            config.agentrouter_last_status = result.get("status")
            if not result["success"]:
                config.agentrouter_last_error = result.get("message")
            
            # Update CLI info if available
            if "details" in result:
                details = result["details"]
                if "cli_version" in details:
                    config.agentrouter_cli_version = details["cli_version"]
                if "base_url" in details:
                    config.agentrouter_cli_installed = True
        
        db.commit()
        
        return {
            "success": result["success"],
            "provider": request.provider,
            **result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test AI provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cli-status")
async def get_agentrouter_cli_status(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Check Qwen CLI installation and status
    
    Returns:
    - Installation status
    - Running status
    - CLI version
    - Base URL
    """
    try:
        config = db.query(AIProviderConfig).filter_by(user_id=user_id).first()
        
        if not config:
            return {
                "success": False,
                "message": "AI provider config not found",
                "installed": False,
                "running": False
            }
        
        # Initialize provider and check CLI
        provider_config = {
            "enabled": config.agentrouter_enabled,
            "api_key": config.agentrouter_api_key,
            "base_url": config.agentrouter_base_url,
            "model": config.agentrouter_model,
            "cli_installed": config.agentrouter_cli_installed
        }
        
        provider = AgentRouterProvider(provider_config)
        cli_status = await provider.check_cli_status()
        
        # Update database
        config.agentrouter_cli_installed = cli_status.get("running", False)
        config.agentrouter_cli_version = cli_status.get("version")
        db.commit()
        
        return {
            "success": True,
            **cli_status
        }
    
    except Exception as e:
        logger.error(f"Failed to check CLI status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_ai_provider_logs(
    user_id: int = 1,  # TODO: Get from auth
    limit: int = 50,
    provider: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get AI provider request logs
    
    Returns recent AI provider requests for analytics:
    - Provider used
    - Success/failure
    - Latency
    - Errors
    - Fallback events
    """
    try:
        query = db.query(AIProviderLog).filter_by(user_id=user_id)
        
        if provider:
            if provider not in ["openrouter", "agentrouter"]:
                raise HTTPException(status_code=400, detail="Invalid provider filter")
            query = query.filter_by(provider=provider)
        
        logs = query.order_by(AIProviderLog.created_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "count": len(logs),
            "logs": [log.to_dict() for log in logs]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI provider logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_ai_provider_statistics(
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """
    Get AI provider usage statistics
    
    Returns aggregated statistics:
    - Total requests per provider
    - Success rate
    - Average latency
    - Fallback frequency
    - Cost tracking (for OpenRouter)
    """
    try:
        config = db.query(AIProviderConfig).filter_by(user_id=user_id).first()
        
        if not config:
            return {
                "success": False,
                "message": "No statistics available"
            }
        
        # Get recent logs for detailed stats
        recent_logs = db.query(AIProviderLog).filter_by(user_id=user_id).order_by(
            AIProviderLog.created_at.desc()
        ).limit(100).all()
        
        # Calculate statistics
        openrouter_logs = [l for l in recent_logs if l.provider == "openrouter"]
        agentrouter_logs = [l for l in recent_logs if l.provider == "agentrouter"]
        
        def calc_stats(logs):
            if not logs:
                return {
                    "total_requests": 0,
                    "success_rate": 0,
                    "avg_latency_ms": 0,
                    "total_recommendations": 0
                }
            
            successful = [l for l in logs if l.success]
            return {
                "total_requests": len(logs),
                "success_rate": round(len(successful) / len(logs) * 100, 2) if logs else 0,
                "avg_latency_ms": round(sum(l.latency_ms or 0 for l in successful) / len(successful), 0) if successful else 0,
                "total_recommendations": sum(l.recommendations_count for l in logs)
            }
        
        return {
            "success": True,
            "statistics": {
                "overall": {
                    "total_requests": config.total_requests,
                    "fallback_triggered": config.fallback_triggered,
                    "last_request_at": config.last_request_at.isoformat() if config.last_request_at else None
                },
                "openrouter": {
                    **calc_stats(openrouter_logs),
                    "credits_remaining": config.openrouter_credits_remaining
                },
                "agentrouter": calc_stats(agentrouter_logs)
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get AI provider statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_available_models():
    """
    Get list of available models for each provider
    
    Returns supported models for:
    - OpenRouter
    - AgentRouter
    """
    return {
        "success": True,
        "providers": {
            "openrouter": {
                "models": [
                    {
                        "id": "qwen/qwen3-max",
                        "name": "Qwen 3 Max",
                        "description": "Advanced reasoning, multi-perspective analysis (Recommended)",
                        "recommended": True
                    },
                    {
                        "id": "deepseek-v3",
                        "name": "DeepSeek V3",
                        "description": "Fast and efficient for trading analysis"
                    },
                    {
                        "id": "anthropic/claude-3.5-sonnet",
                        "name": "Claude 3.5 Sonnet",
                        "description": "High quality, sophisticated reasoning"
                    },
                    {
                        "id": "openai/gpt-4-turbo",
                        "name": "GPT-4 Turbo",
                        "description": "OpenAI's most capable model"
                    }
                ]
            },
            "agentrouter": {
                "models": [
                    {
                        "id": "qwen",
                        "name": "Qwen",
                        "description": "Advanced reasoning via local CLI (Recommended)",
                        "recommended": True
                    },
                    {
                        "id": "claude",
                        "name": "Claude",
                        "description": "Anthropic Claude via local CLI"
                    },
                    {
                        "id": "deepseek-v3.2",
                        "name": "DeepSeek V3.2",
                        "description": "Latest DeepSeek model via CLI"
                    },
                    {
                        "id": "gpt-5",
                        "name": "GPT-5",
                        "description": "OpenAI GPT-5 via local CLI (if available)"
                    }
                ]
            }
        }
    }

