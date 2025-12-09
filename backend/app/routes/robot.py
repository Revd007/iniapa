"""
Robot Trading API Routes
Manages robot trading configuration and execution
"""

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
import logging

from app.database import get_db
from app.models import RobotConfig, TradingMode, AssetClass
from app.services.robot_config_service import RobotConfigService
from app.services.robot_trading_service import robot_service

logger = logging.getLogger(__name__)

router = APIRouter()


class RobotConfigUpdate(BaseModel):
    """Schema for updating robot configuration"""
    enabled: Optional[bool] = None
    min_confidence: Optional[int] = None
    max_positions: Optional[int] = None
    leverage: Optional[int] = None
    capital_per_trade: Optional[float] = None
    trading_mode: Optional[str] = None
    asset_class: Optional[str] = None
    strategies: Optional[List[str]] = None
    max_daily_loss: Optional[float] = None
    max_drawdown_percent: Optional[float] = None
    ai_models: Optional[List[str]] = None
    require_consensus: Optional[bool] = None
    trade_cooldown_seconds: Optional[int] = None
    scan_interval_seconds: Optional[int] = None


class RobotStatusResponse(BaseModel):
    """Robot status response"""
    enabled: bool
    status: str  # 'idle', 'scanning', 'executing'
    total_trades_executed: int
    last_trade_at: Optional[str]
    current_positions: int
    config: dict


@router.get("/config", response_model=dict)
async def get_robot_config(
    environment: str = Query("live", description="Environment: demo or live"),
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Get robot trading configuration for current user
    
    Returns complete robot configuration including:
    - Trading parameters (leverage, capital, confidence)
    - Active strategies
    - Risk management settings
    - Execution statistics
    
    Args:
        environment: 'demo' or 'live' - determines which config to return
    """
    try:
        # Normalize environment
        environment = environment.lower().strip() if environment else "live"
        if environment == "production":
            environment = "live"
        if environment not in ["demo", "live"]:
            environment = "live"
        
        config = RobotConfigService.get_config(db, user_id, environment)
        result = RobotConfigService.to_dict(config)
        result['environment'] = environment
        return result
    except Exception as e:
        logger.error(f"Failed to get robot config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_robot_config(
    updates: RobotConfigUpdate,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Update robot trading configuration
    
    Allows updating any robot setting including:
    - Enable/disable robot
    - Trading parameters (leverage, capital, etc.)
    - Strategy selection
    - Risk management rules
    
    Only provided fields will be updated, others remain unchanged
    """
    try:
        # Convert updates to dict and handle list conversions
        updates_dict = updates.dict(exclude_unset=True)
        
        # Convert list fields to comma-separated strings for DB storage
        if 'strategies' in updates_dict and updates_dict['strategies']:
            updates_dict['strategies'] = ','.join(updates_dict['strategies'])
        if 'ai_models' in updates_dict and updates_dict['ai_models']:
            updates_dict['ai_models'] = ','.join(updates_dict['ai_models'])
        
        # Update config
        config = RobotConfigService.update_config(db, user_id, updates_dict)
        
        return {
            "success": True,
            "message": "Robot configuration updated successfully",
            "config": RobotConfigService.to_dict(config)
        }
    except Exception as e:
        logger.error(f"Failed to update robot config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_robot(
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Toggle robot ON/OFF
    
    Quick endpoint to enable or disable robot trading without
    changing other settings. Safe operation that preserves all
    configuration.
    """
    try:
        config = RobotConfigService.toggle_enabled(db, user_id)
        
        return {
            "success": True,
            "enabled": config.enabled,
            "message": f"Robot {'enabled' if config.enabled else 'disabled'} successfully"
        }
    except Exception as e:
        logger.error(f"Failed to toggle robot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_robot_status(
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Get current robot status and statistics
    
    Returns:
    - Enabled/disabled state
    - Current activity (scanning/executing/idle)
    - Trading statistics (total trades, last trade time)
    - Active positions count
    - Full configuration
    """
    try:
        config = RobotConfigService.get_config(db, user_id)
        
        # TODO: Get actual status from robot executor service
        # For now, return basic status
        status = "idle"
        if config.enabled:
            status = "monitoring"
        
        return {
            "success": True,
            "enabled": config.enabled,
            "status": status,
            "total_trades_executed": config.total_trades_executed or 0,
            "last_trade_at": config.last_trade_at.isoformat() if config.last_trade_at else None,
            "current_positions": 0,  # TODO: Query from trades table
            "config": RobotConfigService.to_dict(config)
        }
    except Exception as e:
        logger.error(f"Failed to get robot status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def trigger_manual_scan(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Manually trigger a robot scan for trading opportunities
    
    Forces the robot to immediately scan the market for signals
    based on current configuration, without waiting for the
    scheduled scan interval.
    
    NOTE: Robot doesn't need to be enabled to scan manually (for testing/debugging).
    """
    try:
        config = RobotConfigService.get_config(db, user_id)
        
        # Allow manual scan even if robot is not enabled (for testing/debugging)
        if not config.enabled:
            logger.warning(f"⚠️ Manual scan triggered for user {user_id} but robot is disabled - scan will proceed anyway")
        
        # Trigger manual scan via robot service (allows scan even if disabled)
        from app.services.robot_trading_service import robot_service
        await robot_service.manual_scan(user_id)
        
        logger.info(f"✅ Manual scan completed for user {user_id}")
        
        return {
            "success": True,
            "message": "Manual scan completed successfully",
            "scanning": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to trigger manual scan: {error_msg}", exc_info=True)
        # Return JSON error response instead of raising HTTPException
        # This allows frontend to see the actual error message
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to trigger scan: {error_msg}",
                "scanning": False,
                "error": error_msg
            }
        )


@router.post("/start")
async def start_robot(
    environment: str = Query("demo", description="Environment: demo or live"),
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Start robot trading - begins automated scanning and execution
    
    Enables the robot and starts the background scheduler that:
    - Scans market every X seconds (configurable)
    - Gets AI recommendations
    - Executes trades if confidence > threshold
    - Applies safety checks (max positions, max loss, cooldown)
    
    Args:
        environment: 'demo' or 'live' - determines which API keys to use
    """
    try:
        # Normalize and validate environment (accept production as alias for live)
        environment = environment.lower().strip() if environment else "demo"
        if environment == "production":
            environment = "live"  # Treat production as live
        if environment not in ["demo", "live"]:
            logger.warning(f"Invalid environment '{environment}', defaulting to 'demo'")
            environment = "demo"  # Default to demo instead of throwing error
        
        # Enable robot in config and set environment
        config = RobotConfigService.get_config(db, user_id)
        config.enabled = True
        config.environment = environment
        db.commit()
        
        # Start robot service with environment
        result = await robot_service.start(user_id, environment)
        
        logger.info(f"Robot started for user {user_id} (environment: {environment})")
        
        return {
            "success": True,
            "message": f"Robot started successfully - now monitoring market ({environment} mode)",
            "enabled": True,
            "environment": environment
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start robot: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_robot(
    environment: str = Query("demo", description="Environment: demo or live"),
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Stop robot trading - stops automated scanning and execution
    
    Disables the robot and stops the background scheduler.
    All configuration is preserved for next start.
    
    This endpoint is called when switching between demo/live modes
    to ensure robot is stopped before environment change.
    """
    try:
        # Normalize and validate environment (accept production as alias for live)
        environment = environment.lower().strip() if environment else "demo"
        if environment == "production":
            environment = "live"  # Treat production as live
        if environment not in ["demo", "live"]:
            logger.warning(f"Invalid environment '{environment}', defaulting to 'demo'")
            environment = "demo"  # Default to demo instead of throwing error
        
        # Disable robot in config
        config = RobotConfigService.get_config(db, user_id)
        config.enabled = False
        # Update environment (already validated above)
        config.environment = environment
        db.commit()
        
        # Stop robot service (pass user_id and environment to update database)
        result = await robot_service.stop(user_id, environment)
        
        logger.info(f"✅ Robot stopped for user {user_id} (environment: {environment})")
        
        return {
            "success": True,
            "message": "Robot stopped successfully - no longer monitoring market",
            "enabled": False,
            "environment": environment
        }
    except Exception as e:
        logger.error(f"Failed to stop robot: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-all")
async def stop_all_robot_activities(
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth context
):
    """
    Emergency stop - immediately disable robot and stop all activities
    
    This is a safety feature to quickly disable the robot in case
    of unexpected behavior or market conditions. All pending
    operations will be cancelled.
    """
    try:
        config = RobotConfigService.get_config(db, user_id)
        config.enabled = False
        db.commit()
        
        # Stop robot service
        await robot_service.stop()
        
        logger.warning(f"Emergency stop triggered for user {user_id}")
        
        return {
            "success": True,
            "message": "Robot stopped successfully. All activities cancelled.",
            "enabled": False
        }
    except Exception as e:
        logger.error(f"Failed to stop robot: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_robot_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = 1,  # TODO: Get from auth context
    limit: int = 10
):
    """
    Get current AI recommendations that robot is monitoring
    
    Returns the latest trading signals from configured AI models
    that meet the robot's confidence threshold and strategy criteria.
    
    These are the signals the robot will consider for execution.
    """
    try:
        from app.routes.ai_recommendations import get_ai_recommendations
        
        config = RobotConfigService.get_config(db, user_id)
        
        # Get recommendations based on robot config
        recommendations = await get_ai_recommendations(
            request=request,
            mode=config.trading_mode.value if config.trading_mode else 'normal',
            asset_class=config.asset_class.value if config.asset_class else 'crypto',
            limit=limit,
            ai_model='qwen'  # Default, can be made configurable
        )
        
        # Filter by robot's confidence threshold
        filtered_recs = [
            rec for rec in recommendations
            if rec.get('confidence', 0) >= config.min_confidence
        ]
        
        return {
            "success": True,
            "count": len(filtered_recs),
            "min_confidence": config.min_confidence,
            "recommendations": filtered_recs
        }
    except Exception as e:
        logger.error(f"Failed to get robot recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


