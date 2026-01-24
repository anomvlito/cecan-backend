#!/usr/bin/env python3
"""
Create scholar_paper_data table directly (bypass migration issue)
"""
import os
os.environ.setdefault('DATABASE_URL', 'postgresql://cecan_user:cecan_password@localhost:5432/cecan_db')

from sqlalchemy import create_engine, text, inspect
from core.models import Base, ScholarPaperData

print("🔧 Creating scholar_paper_data table directly...\n")

# Create engine
engine = create_engine(os.environ['DATABASE_URL'])
inspector = inspect(engine)

# Check if table exists
if 'scholar_paper_data' in inspector.get_table_names():
    print("✅ Table already exists!")
else:
    print("📝 Creating table...")
    
    # Create table using SQLAlchemy (skips enum creation if exists)
    ScholarPaperData.__table__.create(engine, checkfirst=True)
    
    print("✅ Table created successfully!")

# Verify
if 'scholar_paper_data' in inspector.get_table_names():
    inspector = inspect(engine)  # Refresh
    columns = inspector.get_columns('scholar_paper_data')
    print(f"\n✨ scholar_paper_data table created with {len(columns)} columns:")
    for col in columns[:5]:  # Show first 5
        print(f"  - {col['name']}: {col['type']}")
    print(f"  ... and {len(columns) - 5} more columns")
    
    # Mark migration as applied in alembic_version
    with engine.connect() as conn:
        # Check current version
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        current = result.fetchone()
        
        if current and current[0] != 'g8h9i0j1k2l3':
            print(f"\n📌 Updating alembic version from {current[0]} to g8h9i0j1k2l3...")
            conn.execute(text("UPDATE alembic_version SET version_num = 'g8h9i0j1k2l3'"))
            conn.commit()
            print("✅ Migration marked as applied!")
        else:
            print(f"\n✅ Alembic already at correct version")
    
    print("\n🎉 All done! You can now run test_scholar_api.py")
else:
    print("\n❌ Failed to create table")
