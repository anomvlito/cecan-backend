from core.models import Base, create_all_tables
from config import SQLALCHEMY_DATABASE_URL
from sqlalchemy import create_engine

print(f"🚀 Initializing Database with URL: {SQLALCHEMY_DATABASE_URL}")

if "sqlite" in SQLALCHEMY_DATABASE_URL:
    print("❌ ERROR: Still pointing to SQLite. Check .env file!")
    exit(1)

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully in PostgreSQL!")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
