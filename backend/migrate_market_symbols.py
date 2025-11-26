"""
Database Migration Script for MarketSymbols
Updates VARCHAR length for symbol, base_asset, and quote_asset columns
"""

import logging
from sqlalchemy import text
from app.database import get_db_context, engine

logger = logging.getLogger(__name__)

def migrate_market_symbols():
    """Update market_symbols table schema to support longer symbols"""
    try:
        logger.info("🔄 Starting market_symbols migration...")
        
        with get_db_context() as db:
            # Check current column types
            result = db.execute(text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'market_symbols'
                AND column_name IN ('symbol', 'base_asset', 'quote_asset')
            """))
            
            columns = {row[0]: (row[1], row[2]) for row in result}
            logger.info(f"Current columns: {columns}")
            
            migrations = []
            
            # Update symbol column if needed
            if columns.get('symbol', (None, None))[1] and columns['symbol'][1] < 30:
                migrations.append("ALTER TABLE market_symbols ALTER COLUMN symbol TYPE VARCHAR(30)")
                logger.info("  Will update symbol column to VARCHAR(30)")
            
            # Update base_asset column if needed
            if columns.get('base_asset', (None, None))[1] and columns['base_asset'][1] < 20:
                migrations.append("ALTER TABLE market_symbols ALTER COLUMN base_asset TYPE VARCHAR(20)")
                logger.info("  Will update base_asset column to VARCHAR(20)")
            
            # Update quote_asset column if needed (should be fine, but check anyway)
            if columns.get('quote_asset', (None, None))[1] and columns['quote_asset'][1] < 10:
                migrations.append("ALTER TABLE market_symbols ALTER COLUMN quote_asset TYPE VARCHAR(10)")
                logger.info("  Will update quote_asset column to VARCHAR(10)")
            
            # Execute migrations
            if migrations:
                logger.info(f"Executing {len(migrations)} migrations...")
                for migration in migrations:
                    logger.info(f"  Executing: {migration}")
                    db.execute(text(migration))
                
                db.commit()
                logger.info("✅ Market symbols migration completed successfully!")
            else:
                logger.info("✅ Database schema is already up to date!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_market_symbols()

