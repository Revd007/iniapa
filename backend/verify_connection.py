"""
Verify Database Connection
Test connection dengan berbagai password untuk debug
"""

import os
from dotenv import load_dotenv
from urllib.parse import quote_plus, urlparse
import psycopg2

load_dotenv()

print("🔍 Verifying Database Connection...")
print("=" * 60)

# Get DATABASE_URL from .env
db_url = os.getenv("DATABASE_URL", "")
if not db_url:
    print("❌ DATABASE_URL not found in .env file!")
    print("\n💡 Add to .env:")
    print("   DATABASE_URL=postgresql://revian:wokolcoy20.@localhost:5432/tradanalisa")
    exit(1)

print(f"📝 DATABASE_URL from .env:")
print(f"   {db_url[:60]}...")

# Parse URL
try:
    parsed = urlparse(db_url)
    print(f"\n📋 Parsed components:")
    print(f"   Scheme: {parsed.scheme}")
    print(f"   User: {parsed.username}")
    print(f"   Password: {'*' * len(parsed.password) if parsed.password else 'None'}")
    print(f"   Host: {parsed.hostname}")
    print(f"   Port: {parsed.port}")
    print(f"   Database: {parsed.path.lstrip('/')}")
    
    # Test password encoding
    if parsed.password:
        encoded = quote_plus(parsed.password)
        print(f"\n🔐 Password encoding:")
        print(f"   Original: {parsed.password}")
        print(f"   Encoded:  {encoded}")
        
        # Build connection string dengan encoded password
        netloc = f"{parsed.username}:{encoded}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        
        test_url = f"{parsed.scheme}://{netloc}{parsed.path}"
        print(f"\n🧪 Testing connection...")
        print(f"   Connection string: {parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}")
        
        # Test connection
        conn = psycopg2.connect(test_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   ✅ SUCCESS!")
        print(f"   PostgreSQL: {version[:50]}...")
        conn.close()
        
        print(f"\n✅ Connection verified!")
        print(f"\n📝 Correct DATABASE_URL for .env:")
        print(f"   DATABASE_URL={test_url}")
        
except psycopg2.OperationalError as e:
    error_msg = str(e)
    print(f"\n❌ Connection failed: {error_msg}")
    
    if "password authentication failed" in error_msg:
        print("\n💡 Password authentication failed!")
        print("   Solutions:")
        print("   1. Update password di PostgreSQL:")
        print("      psql -U postgres")
        print("      ALTER USER revian WITH PASSWORD 'wokolcoy20.';")
        print("\n   2. Or run: python setup_database.py")
        print("\n   3. Make sure .env has correct password (will auto-encode)")
    elif "does not exist" in error_msg.lower():
        print("\n💡 Database or user does not exist!")
        print("   Run: python setup_database.py")
    else:
        print(f"\n💡 Error: {error_msg}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

