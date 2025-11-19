"""
Database Migration Script
Adds stop_loss, take_profit, sl_order_id, tp_order_id columns to trades table
"""

import sqlite3
import os

def migrate_database():
    """Add new columns to existing database"""
    db_path = "nof1_trading.db"
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet. Will be created on first run.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(trades)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add missing columns
    migrations = []
    
    if 'stop_loss' not in columns:
        migrations.append("ALTER TABLE trades ADD COLUMN stop_loss FLOAT")
    
    if 'take_profit' not in columns:
        migrations.append("ALTER TABLE trades ADD COLUMN take_profit FLOAT")
    
    if 'sl_order_id' not in columns:
        migrations.append("ALTER TABLE trades ADD COLUMN sl_order_id VARCHAR")
    
    if 'tp_order_id' not in columns:
        migrations.append("ALTER TABLE trades ADD COLUMN tp_order_id VARCHAR")
    
    # Execute migrations
    if migrations:
        print(f"Running {len(migrations)} migrations...")
        for migration in migrations:
            print(f"  Executing: {migration}")
            cursor.execute(migration)
        
        conn.commit()
        print("✅ Database migration completed successfully!")
    else:
        print("✅ Database is already up to date!")
    
    conn.close()

if __name__ == "__main__":
    migrate_database()

