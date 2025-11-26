"""
Database Migration Script
Adds environment column to robot_configs table
"""

import logging
from sqlalchemy import text
from app.database import get_db_context, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_environment():
    """Add environment column to robot_configs table if it doesn't exist"""
    try:
        with get_db_context() as db:
            # Check if column already exists
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'robot_configs' AND column_name = 'environment'
            """))
            
            if result.fetchone():
                logger.info("✅ Column 'environment' already exists in robot_configs table")
                return
            
            # Add environment column
            logger.info("Adding 'environment' column to robot_configs table...")
            db.execute(text("""
                ALTER TABLE robot_configs 
                ADD COLUMN environment VARCHAR(10) DEFAULT 'demo'
            """))
            
            # Update existing rows to have 'demo' as default
            db.execute(text("""
                UPDATE robot_configs 
                SET environment = 'demo' 
                WHERE environment IS NULL
            """))
            
            db.commit()
            logger.info("✅ Successfully added 'environment' column to robot_configs table")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def migrate_update_require_consensus():
    """Update require_consensus default to False (since only Qwen is used)"""
    try:
        with get_db_context() as db:
            # Check if we need to update default value
            # Note: PostgreSQL doesn't allow changing default without recreating column
            # So we'll just update existing NULL values
            logger.info("Updating require_consensus values...")
            db.execute(text("""
                UPDATE robot_configs 
                SET require_consensus = FALSE 
                WHERE require_consensus IS NULL OR require_consensus = TRUE
            """))
            
            db.commit()
            logger.info("✅ Successfully updated require_consensus values")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not update require_consensus: {e}")


if __name__ == "__main__":
    logger.info("Starting database migration...")
    try:
        migrate_add_environment()
        migrate_update_require_consensus()
        logger.info("✅ All migrations completed successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        exit(1)

