"""
Database Models for NOF1 Trading Platform
Production-ready schema with proper relationships and constraints
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, 
    ForeignKey, Enum, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


class TradeSide(str, enum.Enum):
    """Trade side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class TradeStatus(str, enum.Enum):
    """Trade status enumeration"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"


class TradingMode(str, enum.Enum):
    """Trading mode enumeration"""
    SCALPER = "scalper"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"
    LONGHOLD = "longhold"


class AssetClass(str, enum.Enum):
    """Asset class enumeration"""
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCKS = "stocks"


class User(Base):
    """User model for multi-user support"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # For future auth
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    robot_config = relationship("RobotConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    api_credentials = relationship("APICredential", back_populates="user", cascade="all, delete-orphan")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    withdrawal_history = relationship("WithdrawalHistory", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"


class UserSettings(Base):
    """User settings including pinned symbols"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Pinned symbols (comma-separated for each asset class)
    pinned_crypto_symbols = Column(String(500), default="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT")
    pinned_forex_symbols = Column(String(500), default="")
    pinned_stocks_symbols = Column(String(500), default="")
    
    # Other settings
    default_leverage = Column(Integer, default=25)
    default_capital_per_trade = Column(Float, default=5.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="user_settings")
    
    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"


class APICredential(Base):
    """Store OAuth tokens and broker credentials per user"""
    __tablename__ = "api_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Binance OAuth tokens (for user's own account)
    binance_access_token = Column(Text)  # OAuth access token
    binance_refresh_token = Column(Text)  # OAuth refresh token
    binance_token_expires_at = Column(DateTime(timezone=True))
    binance_user_id = Column(String(100))  # Binance user ID
    
    # Binance API keys (legacy, for platform trading)
    binance_api_key = Column(String(255))
    binance_api_secret = Column(String(255))
    binance_testnet = Column(Boolean, default=True)
    environment = Column(String(10), default="demo")  # 'demo' or 'live' - determines which API keys to use
    
    # MT5 OAuth/credentials
    mt5_access_token = Column(Text)
    mt5_refresh_token = Column(Text)
    mt5_login = Column(String(100))
    mt5_password = Column(String(255))
    mt5_server = Column(String(100))
    mt5_env = Column(String(20), default="demo")
    
    # Account info cache
    broker_name = Column(String(50))  # 'binance' or 'mt5'
    account_balance = Column(Float)
    account_currency = Column(String(10))
    last_balance_update = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="api_credentials")
    
    __table_args__ = (
        Index("idx_api_credentials_user", "user_id"),
    )


class TradeMode(str, enum.Enum):
    """Trade execution mode"""
    DEMO = "demo"  # Paper trading, simulation
    LIVE = "live"  # OAuth-authenticated, real trading


class Trade(Base):
    """Trade model with comprehensive tracking"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1)
    
    # Execution mode: demo (simulation) or live (OAuth)
    execution_mode = Column(Enum(TradeMode), default=TradeMode.DEMO, nullable=False)
    
    # Trade details
    symbol = Column(String(20), nullable=False, index=True)
    asset_class = Column(Enum(AssetClass), default=AssetClass.CRYPTO, nullable=False)
    side = Column(Enum(TradeSide), nullable=False)
    order_type = Column(Enum(OrderType), default=OrderType.MARKET, nullable=False)
    
    # Quantities and prices
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    
    # Leverage and margin
    leverage = Column(Float, default=1.0, nullable=False)
    margin_used = Column(Float)
    total_value = Column(Float, nullable=False)
    
    # P&L tracking
    profit_loss = Column(Float)
    profit_loss_percent = Column(Float)
    is_win = Column(Boolean)
    
    # Risk management
    stop_loss = Column(Float)
    take_profit = Column(Float)
    trailing_stop = Column(Float)
    
    # Status and mode
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN, nullable=False, index=True)
    trading_mode = Column(Enum(TradingMode), default=TradingMode.NORMAL, nullable=False)
    
    # AI integration
    ai_confidence = Column(Float)
    ai_reason = Column(Text)
    ai_model = Column(String(50))  # qwen (DeepSeek deprecated)
    
    # External order IDs
    binance_order_id = Column(String(100))
    sl_order_id = Column(String(100))
    tp_order_id = Column(String(100))
    mt5_ticket = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="trades")
    
    __table_args__ = (
        Index("idx_trades_user_status", "user_id", "status"),
        Index("idx_trades_symbol_status", "symbol", "status"),
        Index("idx_trades_execution_mode", "execution_mode", "status"),
        Index("idx_trades_created", "created_at"),
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        CheckConstraint("leverage >= 1", name="check_leverage_min"),
        CheckConstraint("entry_price > 0", name="check_entry_price_positive"),
    )
    
    def __repr__(self):
        return f"<Trade {self.symbol} {self.side} {self.quantity} @ {self.entry_price}>"


class RobotConfig(Base):
    """Robot trading configuration per user"""
    __tablename__ = "robot_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Robot settings
    enabled = Column(Boolean, default=False, nullable=False)
    min_confidence = Column(Integer, default=75, nullable=False)
    max_positions = Column(Integer, default=3, nullable=False)
    leverage = Column(Integer, default=25, nullable=False)
    capital_per_trade = Column(Float, default=5.0, nullable=False)
    
    # Trading mode and asset class
    trading_mode = Column(Enum(TradingMode), default=TradingMode.NORMAL)
    asset_class = Column(Enum(AssetClass), default=AssetClass.CRYPTO)
    
    # Strategy selection (JSON array as comma-separated string)
    strategies = Column(String(500), default="Breakout,Trend Fusion")
    
    # Risk management
    max_daily_loss = Column(Float, default=50.0)
    max_drawdown_percent = Column(Float, default=20.0)
    daily_profit_target = Column(Float)
    
    # AI model preferences
    ai_models = Column(String(200), default="qwen")  # Comma-separated (qwen only)
    require_consensus = Column(Boolean, default=False)  # Not needed since only Qwen
    
    # Environment (demo/live)
    environment = Column(String(10), default="demo")  # 'demo' or 'live'
    
    # Cooldown settings
    trade_cooldown_seconds = Column(Integer, default=30)
    scan_interval_seconds = Column(Integer, default=30)
    
    # Statistics
    total_trades_executed = Column(Integer, default=0)
    last_trade_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="robot_config")
    
    __table_args__ = (
        CheckConstraint("min_confidence >= 50 AND min_confidence <= 100", name="check_confidence_range"),
        CheckConstraint("max_positions > 0 AND max_positions <= 10", name="check_max_positions"),
        CheckConstraint("leverage >= 1 AND leverage <= 125", name="check_leverage_range"),
        CheckConstraint("capital_per_trade > 0", name="check_capital_positive"),
    )


class PerformanceMetric(Base):
    """Daily performance metrics aggregation"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1)
    
    # Date tracking
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    asset_class = Column(Enum(AssetClass), default=AssetClass.CRYPTO)
    
    # Trade counts
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    
    # P&L metrics
    total_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    
    # Performance metrics
    win_rate = Column(Float, default=0.0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    risk_reward_ratio = Column(Float, default=0.0)
    
    # Volume metrics
    total_volume = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("user_id", "date", "asset_class", name="uq_user_date_asset"),
        Index("idx_perf_user_date", "user_id", "date"),
    )


class MarketSymbol(Base):
    """Cache for available market symbols"""
    __tablename__ = "market_symbols"
    
    id = Column(Integer, primary_key=True, index=True)
    
    symbol = Column(String(30), unique=True, nullable=False, index=True)  # Increased for longer symbols like TURTLEUSDT, GIGGLEUSDT
    base_asset = Column(String(20), nullable=False)  # Increased for longer base assets
    quote_asset = Column(String(10), nullable=False)  # USDT, USD, etc.
    asset_class = Column(Enum(AssetClass), nullable=False)
    
    # Symbol metadata
    is_active = Column(Boolean, default=True)
    min_quantity = Column(Float)
    max_quantity = Column(Float)
    tick_size = Column(Float)
    
    # For sorting/filtering
    volume_24h = Column(Float)
    price_change_24h = Column(Float)
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index("idx_symbol_asset_class", "asset_class", "is_active"),
    )


class WithdrawalStatus(str, enum.Enum):
    """Withdrawal status enumeration"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WithdrawalHistory(Base):
    """Withdrawal history tracking"""
    __tablename__ = "withdrawal_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1)
    
    # Withdrawal details
    asset = Column(String(10), nullable=False)  # USDT, BTC, etc.
    amount = Column(Float, nullable=False)
    address = Column(String(255), nullable=False)
    network = Column(String(50))  # BSC, ETH, TRX, etc.
    address_tag = Column(String(255))  # For XRP, XLM, etc.
    name = Column(String(255))  # Description/name
    
    # Status and tracking
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False, index=True)
    withdrawal_id = Column(String(100))  # Binance withdrawal ID
    tx_id = Column(String(255))  # Transaction hash/ID
    
    # Environment
    environment = Column(String(10), default="demo", nullable=False)  # 'demo' or 'live'
    
    # Error tracking
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="withdrawal_history")
    
    __table_args__ = (
        Index("idx_withdrawal_user_status", "user_id", "status"),
        Index("idx_withdrawal_environment", "environment", "status"),
        Index("idx_withdrawal_created", "created_at"),
        CheckConstraint("amount > 0", name="check_withdrawal_amount_positive"),
    )
    
    def __repr__(self):
        return f"<WithdrawalHistory {self.asset} {self.amount} to {self.address[:10]}...>"
