"""
Market Symbol Synchronization Service
Fetches all available symbols from Binance and syncs to database
"""

import logging
from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarketSymbol, AssetClass

logger = logging.getLogger(__name__)


class MarketSyncService:
    """Service to sync market symbols from exchanges"""
    
    def __init__(self, binance_service):
        self.binance_service = binance_service
    
    async def sync_crypto_symbols(self, db: Session) -> int:
        """
        Fetch ALL crypto symbols from Binance and sync to database
        Returns: number of symbols synced
        """
        try:
            logger.info("Syncing crypto symbols from Binance...")
            
            # Get exchange info from Binance
            exchange_info = await self.binance_service.get_exchange_info()
            
            if not exchange_info or 'symbols' not in exchange_info:
                logger.error("Failed to fetch exchange info from Binance")
                return 0
            
            # Get 24h ticker data for volume filtering
            tickers_24h = await self.binance_service.get_24h_tickers()
            ticker_map = {t['symbol']: t for t in tickers_24h} if tickers_24h else {}
            
            synced_count = 0
            updated_count = 0
            
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                
                # Filter: only USDT pairs
                if not symbol.endswith('USDT'):
                    continue
                
                # Filter: only TRADING status
                if symbol_info.get('status') != 'TRADING':
                    continue
                
                # Get 24h data
                ticker_data = ticker_map.get(symbol, {})
                volume_24h = float(ticker_data.get('quoteVolume', 0))
                price_change_24h = float(ticker_data.get('priceChangePercent', 0))
                
                # Filter by minimum volume (lowered to get more symbols)
                # Only filter if volume is 0 or negative (invalid data)
                if volume_24h <= 0:
                    continue
                
                # Extract base and quote assets
                base_asset = symbol_info['baseAsset']
                quote_asset = symbol_info['quoteAsset']
                
                # Get or create symbol in database
                db_symbol = db.query(MarketSymbol).filter_by(symbol=symbol).first()
                
                if db_symbol:
                    # Update existing
                    db_symbol.is_active = True
                    db_symbol.volume_24h = volume_24h
                    db_symbol.price_change_24h = price_change_24h
                    db_symbol.last_updated = datetime.utcnow()
                    updated_count += 1
                else:
                    # Create new
                    db_symbol = MarketSymbol(
                        symbol=symbol,
                        base_asset=base_asset,
                        quote_asset=quote_asset,
                        asset_class=AssetClass.CRYPTO,
                        is_active=True,
                        volume_24h=volume_24h,
                        price_change_24h=price_change_24h,
                        # Get trading rules
                        min_quantity=self._get_min_quantity(symbol_info),
                        max_quantity=self._get_max_quantity(symbol_info),
                        tick_size=self._get_tick_size(symbol_info),
                    )
                    db.add(db_symbol)
                    synced_count += 1
            
            db.commit()
            
            total = synced_count + updated_count
            logger.info(f"✅ Synced {total} symbols ({synced_count} new, {updated_count} updated)")
            return total
            
        except Exception as e:
            logger.error(f"Failed to sync crypto symbols: {e}")
            db.rollback()
            return 0
    
    def _get_min_quantity(self, symbol_info: Dict) -> float:
        """Extract minimum quantity from symbol filters"""
        try:
            for filter in symbol_info.get('filters', []):
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['minQty'])
        except:
            pass
        return 0.0
    
    def _get_max_quantity(self, symbol_info: Dict) -> float:
        """Extract maximum quantity from symbol filters"""
        try:
            for filter in symbol_info.get('filters', []):
                if filter['filterType'] == 'LOT_SIZE':
                    return float(filter['maxQty'])
        except:
            pass
        return 0.0
    
    def _get_tick_size(self, symbol_info: Dict) -> float:
        """Extract tick size from symbol filters"""
        try:
            for filter in symbol_info.get('filters', []):
                if filter['filterType'] == 'PRICE_FILTER':
                    return float(filter['tickSize'])
        except:
            pass
        return 0.0
    
    async def get_active_symbols(
        self, 
        db: Session, 
        asset_class: AssetClass = AssetClass.CRYPTO,
        limit: int = None
    ) -> List[str]:
        """
        Get list of active symbols from database
        Sorted by 24h volume (most liquid first)
        """
        query = db.query(MarketSymbol).filter(
            MarketSymbol.asset_class == asset_class,
            MarketSymbol.is_active == True
        ).order_by(MarketSymbol.volume_24h.desc())
        
        if limit:
            query = query.limit(limit)
        
        symbols = query.all()
        return [s.symbol for s in symbols]
    
    async def get_symbols_for_ai(
        self,
        db: Session,
        asset_class: AssetClass = AssetClass.CRYPTO,
        max_symbols: int = None
    ) -> List[Dict]:
        """
        Get top liquid symbols for AI analysis
        Returns list with symbol metadata
        """
        max_symbols = max_symbols or settings.MAX_AI_SYMBOLS
        
        symbols = db.query(MarketSymbol).filter(
            MarketSymbol.asset_class == asset_class,
            MarketSymbol.is_active == True
        ).order_by(MarketSymbol.volume_24h.desc()).limit(max_symbols).all()
        
        return [
            {
                'symbol': s.symbol,
                'base_asset': s.base_asset,
                'volume_24h': s.volume_24h,
                'price_change_24h': s.price_change_24h,
            }
            for s in symbols
        ]

