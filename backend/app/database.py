"""
Database configuration and session management
Uses SQLite for simplicity with SQLAlchemy ORM
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config import settings

# Create database engine with optimizations for faster startup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=False,  # Disable connection health checks for faster startup
    echo=False,  # Disable SQL logging for faster startup
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class Trade(Base):
    """Trade model for storing executed trades"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # BUY or SELL
    order_type = Column(String)  # MARKET, LIMIT, etc.
    quantity = Column(Float)
    price = Column(Float)
    total_value = Column(Float)
    leverage = Column(Float, default=1.0)
    
    # Trade outcome
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    profit_loss = Column(Float, nullable=True)
    profit_loss_percent = Column(Float, nullable=True)
    is_win = Column(Boolean, nullable=True)
    
    # Metadata
    trading_mode = Column(String)
    ai_confidence = Column(Float, nullable=True)
    ai_reason = Column(String, nullable=True)
    
    status = Column(String, default="OPEN")  # OPEN, CLOSED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Binance order ID
    binance_order_id = Column(String, nullable=True)
    
    # Stop Loss / Take Profit
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    sl_order_id = Column(String, nullable=True)
    tp_order_id = Column(String, nullable=True)


class PerformanceMetric(Base):
    """Performance metrics model for tracking daily statistics"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Daily metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    total_profit = Column(Float, default=0.0)
    total_loss = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    
    # Risk metrics
    avg_risk_reward_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)
    
    # Trading mode breakdown
    trading_mode = Column(String, nullable=True)


def init_db():
    """Initialize database tables - optimized for fast startup"""
    # Use checkfirst=True to skip if tables already exist (faster)
    Base.metadata.create_all(bind=engine, checkfirst=True)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

