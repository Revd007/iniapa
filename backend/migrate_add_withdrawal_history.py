"""
Migration: Add withdrawal_history table
Run this to add the withdrawal_history table to the database
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from app.models import Base, WithdrawalHistory

def migrate():
    """Create withdrawal_history table"""
    print("🔄 Creating withdrawal_history table...")
    
    try:
        # Create the table
        WithdrawalHistory.__table__.create(engine, checkfirst=True)
        print("✅ withdrawal_history table created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating withdrawal_history table: {e}")
        return False

if __name__ == "__main__":
    migrate()

