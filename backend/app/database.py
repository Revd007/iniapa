"""
Database configuration for PostgreSQL
Production-ready with connection pooling and proper error handling
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# Create engine with connection pooling for production
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,  # Number of connections to keep open
    max_overflow=40,  # Additional connections when pool is full
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session
    Automatically handles commit/rollback and closes session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database session outside of FastAPI
    Usage:
        with get_db_context() as db:
            # do stuff
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def migrate_market_symbols_schema(db):
    """Migrate market_symbols table schema if needed"""
    try:
        from sqlalchemy import text
        
        # Check and update symbol column
        result = db.execute(text("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'market_symbols' AND column_name = 'symbol'
        """))
        row = result.fetchone()
        if row and row[0] and row[0] < 30:
            logger.info("Updating market_symbols.symbol to VARCHAR(30)...")
            db.execute(text("ALTER TABLE market_symbols ALTER COLUMN symbol TYPE VARCHAR(30)"))
        
        # Check and update base_asset column
        result = db.execute(text("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'market_symbols' AND column_name = 'base_asset'
        """))
        row = result.fetchone()
        if row and row[0] and row[0] < 20:
            logger.info("Updating market_symbols.base_asset to VARCHAR(20)...")
            db.execute(text("ALTER TABLE market_symbols ALTER COLUMN base_asset TYPE VARCHAR(20)"))
        
        db.commit()
        logger.info("✅ Market symbols schema migration completed")
    except Exception as e:
        logger.warning(f"Schema migration check failed (may not exist yet): {e}")
        db.rollback()

def init_db():
    """
    Initialize database:
    - Create all tables
    - Create default user if not exists
    - Seed initial data
    """
    from app.models import Base, User
    
    logger.info("Initializing database...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database tables created")
    
    # Migrate market_symbols schema if needed
    with get_db_context() as db:
        migrate_market_symbols_schema(db)
    
    # Create default user for development
    with get_db_context() as db:
        default_user = db.query(User).filter_by(id=1).first()
        if not default_user:
            default_user = User(
                id=1,
                email="trader@tradanalisa.com",
                username="trader",
                is_active=True,
                is_admin=True
            )
            db.add(default_user)
            db.commit()
            logger.info("✓ Default user created")
        else:
            logger.info("✓ Default user already exists")
    
    logger.info("✅ Database initialization complete")


def check_db_connection():
    """Check if database connection is working"""
    try:
        # Test connection dengan simple query (SQLAlchemy 2.0 syntax)
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            result.fetchone()
        logger.info("✓ Database connection successful")
        return True
    except Exception as e:
        error_msg = str(e)
        logger.error(f"✗ Database connection failed: {error_msg}")
        
        # Provide helpful error messages
        if "password authentication failed" in error_msg:
            logger.error("💡 Password authentication failed. Check:")
            logger.error("   1. Password di .env file (tulis password asli, akan auto-encode)")
            logger.error("   2. Password di PostgreSQL harus match")
            logger.error("   3. Run: python setup_database.py untuk update password")
        elif "could not translate host name" in error_msg:
            logger.error("💡 Host resolution failed. Check DATABASE_URL format.")
        elif "does not exist" in error_msg.lower():
            logger.error("💡 Database or user does not exist. Run: python setup_database.py")
        
        return False


# Event listeners for connection pool monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log when new connection is created"""
    logger.debug("Database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when connection is checked out from pool"""
    logger.debug("Connection checked out from pool")


# Import models after engine is created (for backwards compatibility)
from app.models import (
    User, Trade, RobotConfig, PerformanceMetric, 
    MarketSymbol, APICredential
)

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "get_db_context",
    "init_db",
    "check_db_connection",
    "User",
    "Trade",
    "RobotConfig",
    "PerformanceMetric",
    "MarketSymbol",
    "APICredential",
]
