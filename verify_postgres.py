import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Load env variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found in environment.")
    sys.exit(1)

try:
    print(f"Connecting to: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("\n--- PostgreSQL Tables ---")
    if not tables:
        print("⚠️  No tables found! The migration did NOT apply.")
    else:
        print(f"✅ Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table}")
            
    # Check for specific expected table
    if "publicaciones" in tables:
        print("\nSUCCESS: 'publicaciones' table exists.")
    else:
        print("\nFAILURE: Critical table 'publicaciones' is missing.")

except Exception as e:
    print(f"\n❌ Connection Error: {e}")
