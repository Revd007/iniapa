"""
Robot Config Service
Manages robot trading configuration in database
"""

import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session

from app.models import RobotConfig, TradingMode, AssetClass

logger = logging.getLogger(__name__)


class RobotConfigService:
    """Service to manage robot trading configuration"""
    
    @staticmethod
    def get_config(db: Session, user_id: int = 1) -> Optional[RobotConfig]:
        """Get robot config for user, create if not exists"""
        config = db.query(RobotConfig).filter_by(user_id=user_id).first()
        
        if not config:
            # Create default config - More aggressive settings for testing
            config = RobotConfig(
                user_id=user_id,
                enabled=False,
                min_confidence=65,  # Lowered from 75 to 65 for more opportunities
                max_positions=3,
                leverage=25,
                capital_per_trade=5.0,
                trading_mode=TradingMode.NORMAL,
                asset_class=AssetClass.CRYPTO,
                strategies="Breakout,Trend Fusion",
                max_daily_loss=50.0,
                max_drawdown_percent=20.0,
                ai_models="qwen,deepseek",
                require_consensus=True,
                trade_cooldown_seconds=30,  # 30 seconds cooldown (less conservative)
                scan_interval_seconds=30,  # Scan every 30 seconds
            )
            db.add(config)
            db.commit()
            db.refresh(config)
            logger.info(f"Created default robot config for user {user_id}")
        
        return config
    
    @staticmethod
    def update_config(
        db: Session,
        user_id: int,
        updates: Dict
    ) -> RobotConfig:
        """Update robot config with provided fields"""
        config = RobotConfigService.get_config(db, user_id)
        
        # Update fields
        for key, value in updates.items():
            if hasattr(config, key):
                # Handle enum conversions
                if key == 'trading_mode' and isinstance(value, str):
                    value = TradingMode(value)
                elif key == 'asset_class' and isinstance(value, str):
                    value = AssetClass(value)
                
                setattr(config, key, value)
        
        db.commit()
        db.refresh(config)
        logger.info(f"Updated robot config for user {user_id}: {updates}")
        return config
    
    @staticmethod
    def toggle_enabled(db: Session, user_id: int) -> RobotConfig:
        """Toggle robot enabled status"""
        config = RobotConfigService.get_config(db, user_id)
        config.enabled = not config.enabled
        db.commit()
        db.refresh(config)
        logger.info(f"Robot {'enabled' if config.enabled else 'disabled'} for user {user_id}")
        return config
    
    @staticmethod
    def increment_trade_count(db: Session, user_id: int):
        """Increment total trades executed counter"""
        from datetime import datetime, timezone
        config = RobotConfigService.get_config(db, user_id)
        config.total_trades_executed += 1
        config.last_trade_at = datetime.now(timezone.utc)
        db.commit()
    
    @staticmethod
    def to_dict(config: RobotConfig) -> Dict:
        """Convert config to dictionary for API response"""
        return {
            'enabled': config.enabled,
            'min_confidence': config.min_confidence,
            'max_positions': config.max_positions,
            'leverage': config.leverage,
            'capital_per_trade': config.capital_per_trade,
            'trading_mode': config.trading_mode.value if config.trading_mode else 'normal',
            'asset_class': config.asset_class.value if config.asset_class else 'crypto',
            'strategies': config.strategies.split(',') if config.strategies else [],
            'max_daily_loss': config.max_daily_loss,
            'max_drawdown_percent': config.max_drawdown_percent,
            'ai_models': config.ai_models.split(',') if config.ai_models else [],
            'require_consensus': config.require_consensus,
            'trade_cooldown_seconds': config.trade_cooldown_seconds,
            'scan_interval_seconds': config.scan_interval_seconds,
            'total_trades_executed': config.total_trades_executed,
            'last_trade_at': config.last_trade_at.isoformat() if config.last_trade_at else None,
        }

