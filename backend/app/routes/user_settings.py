"""
User Settings Routes - Manage user preferences including pinned symbols
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import UserSettings, AssetClass
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class PinnedSymbolsUpdate(BaseModel):
    asset_class: str
    symbols: List[str]


class PinnedSymbolsResponse(BaseModel):
    asset_class: str
    symbols: List[str]


@router.get("/pinned-symbols")
async def get_pinned_symbols(
    asset_class: str,
    db: Session = Depends(get_db),
    user_id: int = 1  # Default user for now
):
    """Get user's pinned symbols for specific asset class"""
    try:
        settings = db.query(UserSettings).filter_by(user_id=user_id).first()
        
        if not settings:
            # Create default settings
            settings = UserSettings(
                user_id=user_id,
                pinned_crypto_symbols="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT",
                pinned_forex_symbols="",
                pinned_stocks_symbols=""
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        # Get pinned symbols based on asset class
        if asset_class == "crypto":
            symbols_str = settings.pinned_crypto_symbols
        elif asset_class == "forex":
            symbols_str = settings.pinned_forex_symbols
        elif asset_class == "stocks":
            symbols_str = settings.pinned_stocks_symbols
        else:
            raise HTTPException(status_code=400, detail="Invalid asset class")
        
        # Parse comma-separated string to list
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()] if symbols_str else []
        
        logger.info(f"Retrieved pinned symbols for user {user_id}, {asset_class}: {symbols}")
        
        return {
            "asset_class": asset_class,
            "symbols": symbols
        }
        
    except Exception as e:
        logger.error(f"Failed to get pinned symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pinned-symbols")
async def update_pinned_symbols(
    data: PinnedSymbolsUpdate,
    db: Session = Depends(get_db),
    user_id: int = 1  # Default user for now
):
    """Update user's pinned symbols for specific asset class"""
    try:
        settings = db.query(UserSettings).filter_by(user_id=user_id).first()
        
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
        
        # Convert list to comma-separated string
        symbols_str = ",".join(data.symbols)
        
        # Update based on asset class
        if data.asset_class == "crypto":
            settings.pinned_crypto_symbols = symbols_str
        elif data.asset_class == "forex":
            settings.pinned_forex_symbols = symbols_str
        elif data.asset_class == "stocks":
            settings.pinned_stocks_symbols = symbols_str
        else:
            raise HTTPException(status_code=400, detail="Invalid asset class")
        
        db.commit()
        db.refresh(settings)
        
        logger.info(f"Updated pinned symbols for user {user_id}, {data.asset_class}: {data.symbols}")
        
        return {
            "success": True,
            "asset_class": data.asset_class,
            "symbols": data.symbols
        }
        
    except Exception as e:
        logger.error(f"Failed to update pinned symbols: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

