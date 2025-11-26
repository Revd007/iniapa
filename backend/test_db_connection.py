"""
Quick Database Connection Test
Test apakah PostgreSQL connection berhasil
"""

import sys
from urllib.parse import quote_plus

# Test dengan password yang berbeda
passwords_to_test = [
    "wokolcoy20.",
    "Wokolcoy@20.",
    "Wokolcoy20.",
]

print("🧪 Testing PostgreSQL Connection...")
print("=" * 60)

for password in passwords_to_test:
    encoded = quote_plus(password)
    connection_string = f"postgresql://revian:{encoded}@localhost:5432/tradanalisa"
    
    print(f"\n📝 Testing password: {password}")
    print(f"   Encoded: {encoded}")
    print(f"   Connection: postgresql://revian:***@localhost:5432/tradanalisa")
    
    try:
        import psycopg2
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   ✅ SUCCESS! PostgreSQL version: {version[:50]}...")
        conn.close()
        
        print(f"\n✅ CORRECT PASSWORD: {password}")
        print(f"✅ CORRECT ENCODED: {encoded}")
        print(f"\n📝 Update .env file:")
        print(f"   DATABASE_URL=postgresql://revian:{encoded}@localhost:5432/tradanalisa")
        sys.exit(0)
        
    except psycopg2.OperationalError as e:
        if "password authentication failed" in str(e):
            print(f"   ❌ Password salah")
        elif "database" in str(e).lower() and "does not exist" in str(e).lower():
            print(f"   ❌ Database 'tradanalisa' tidak ada")
        elif "role" in str(e).lower() and "does not exist" in str(e).lower():
            print(f"   ❌ User 'revian' tidak ada")
        else:
            print(f"   ❌ Error: {e}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("❌ Semua password gagal!")
print("\n💡 Solusi:")
print("   1. Pastikan PostgreSQL running")
print("   2. Create user dan database:")
print("      psql -U postgres")
print("      CREATE DATABASE tradanalisa;")
print("      CREATE USER revian WITH PASSWORD 'wokolcoy20.';")
print("      GRANT ALL PRIVILEGES ON DATABASE tradanalisa TO revian;")
print("   3. Atau run: python setup_database.py")

