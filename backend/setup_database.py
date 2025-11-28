"""
Database Setup Script
Membantu setup PostgreSQL database dan user untuk TradAnalisa
"""

import psycopg2
from psycopg2 import sql
import sys

# Database configuration
DB_NAME = "tradanalisa"
DB_USER = "revian"
DB_PASSWORD = "Wokolcoy@20."  # Password asli dengan @
DB_HOST = "localhost"
DB_PORT = 5432

def setup_database():
    """Setup database dan user"""
    print("🔧 Setting up PostgreSQL database...")
    
    # Connect sebagai postgres superuser
    try:
        print(f"📡 Connecting to PostgreSQL as postgres user...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user="postgres",
            password=input("Enter postgres superuser password (or press Enter if no password): ") or ""
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("\n💡 Tips:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Try: sudo -u postgres psql (Linux/Mac)")
        print("   3. Or use pgAdmin to connect")
        return False
    
    try:
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        if cursor.fetchone():
            print(f"✓ Database '{DB_NAME}' already exists")
        else:
            # Create database
            print(f"📦 Creating database '{DB_NAME}'...")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(DB_NAME)
            ))
            print(f"✅ Database '{DB_NAME}' created")
        
        # Check if user exists
        cursor.execute(
            "SELECT 1 FROM pg_user WHERE usename = %s",
            (DB_USER,)
        )
        if cursor.fetchone():
            print(f"✓ User '{DB_USER}' already exists")
            # Update password
            print(f"🔑 Updating password for user '{DB_USER}'...")
            cursor.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                    sql.Identifier(DB_USER)
                ),
                (DB_PASSWORD,)
            )
            print(f"✅ Password updated")
        else:
            # Create user
            print(f"👤 Creating user '{DB_USER}'...")
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(DB_USER)
                ),
                (DB_PASSWORD,)
            )
            print(f"✅ User '{DB_USER}' created")
        
        # Grant privileges
        print(f"🔐 Granting privileges...")
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(DB_NAME),
                sql.Identifier(DB_USER)
            )
        )
        
        # Connect to new database to grant schema privileges
        conn.close()
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user="postgres",
            password=input("Enter postgres password again (or press Enter): ") or ""
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(
            sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(
                sql.Identifier(DB_USER)
            )
        )
        cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}".format(DB_USER))
        cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {}".format(DB_USER))
        cursor.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}".format(DB_USER))
        cursor.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}".format(DB_USER))
        
        print(f"✅ Privileges granted")
        
        conn.close()
        print("\n✅ Database setup complete!")
        print(f"\n📝 Connection string:")
        print(f"   DATABASE_URL=postgresql://{DB_USER}:Wokolcoy%4020.@localhost:5432/{DB_NAME}")
        print(f"\n   (Password dengan @ harus di-encode: Wokolcoy@20. → Wokolcoy%4020.)")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_connection():
    """Test connection dengan user baru"""
    print("\n🧪 Testing connection...")
    from urllib.parse import quote_plus
    
    # URL-encode password
    encoded_password = quote_plus(DB_PASSWORD)
    connection_string = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Connection successful!")
        print(f"   PostgreSQL version: {version[:50]}...")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("TradAnalisa - PostgreSQL Database Setup")
    print("=" * 60)
    print()
    
    if setup_database():
        test_connection()
    else:
        print("\n❌ Setup failed. Please check PostgreSQL is running and try again.")
        sys.exit(1)

