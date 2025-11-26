"""
Update existing OPEN trades from DEMO to LIVE execution_mode
This is needed when robot was creating trades without execution_mode set properly
"""

from app.database import SessionLocal
from app.models import Trade, TradeMode

def update_trades_to_live():
    """Update all OPEN trades to LIVE execution_mode"""
    db = SessionLocal()
    try:
        # Find all OPEN trades with DEMO execution_mode
        trades = db.query(Trade).filter(
            Trade.status == "OPEN",
            Trade.execution_mode == TradeMode.DEMO
        ).all()
        
        print(f"Found {len(trades)} OPEN trades with DEMO execution_mode")
        
        for trade in trades:
            print(f"  Updating {trade.symbol}: {trade.execution_mode} -> LIVE")
            trade.execution_mode = TradeMode.LIVE
        
        db.commit()
        print(f"✅ Updated {len(trades)} trades to LIVE execution_mode")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_trades_to_live()

