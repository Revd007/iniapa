"""
Database Migration Script
Adds environment column to api_credentials table
"""

import logging
from sqlalchemy import text
from app.database import get_db_context, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_environment_to_api_credentials():
    """Add environment column to api_credentials table if it doesn't exist"""
    try:
        with get_db_context() as db:
            # Check if column already exists
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'api_credentials' AND column_name = 'environment'
            """))
            
            if result.fetchone():
                logger.info("✅ Column 'environment' already exists in api_credentials table")
                return
            
            # Add environment column
            logger.info("Adding 'environment' column to api_credentials table...")
            db.execute(text("""
                ALTER TABLE api_credentials 
                ADD COLUMN environment VARCHAR(10) DEFAULT 'demo'
            """))
            
            # Update existing rows to have 'demo' as default
            db.execute(text("""
                UPDATE api_credentials 
                SET environment = 'demo' 
                WHERE environment IS NULL
            """))
            
            db.commit()
            logger.info("✅ Successfully added 'environment' column to api_credentials table")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


    try:
        # Create the table
        WithdrawalHistory.__table__.create(engine, checkfirst=True)
        print("✅ withdrawal_history table created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating withdrawal_history table: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting database migration for api_credentials...")
    try:
        migrate_add_environment_to_api_credentials()
        logger.info("✅ Migration completed successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        exit(1)

