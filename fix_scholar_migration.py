#!/usr/bin/env python3
"""
Verify and fix Scholar table migration
"""
import subprocess
import sys

print("🔍 Checking Alembic migration status...\n")

# Check current migration
result = subprocess.run(
    ["alembic", "current"],
    capture_output=True,
    text=True,
    cwd="."
)

print("Current migration:")
print(result.stdout)
print(result.stderr)

print("\n📋 Checking migration heads...")
result = subprocess.run(
    ["alembic", "heads"],
    capture_output=True,
    text=True,
    cwd="."
)

print(result.stdout)
print(result.stderr)

print("\n🚀 Applying migrations to head...")
result = subprocess.run(
    ["alembic", "upgrade", "head"],
    capture_output=True,
    text=True,
    cwd="."
)

print(result.stdout)
if result.stderr:
    print("Errors:", result.stderr)

if result.returncode == 0:
    print("\n✅ Migrations applied successfully!")
else:
    print(f"\n❌ Migration failed with code {result.returncode}")
    sys.exit(1)

# Verify table exists
print("\n🔍 Verifying scholar_paper_data table exists...")

import os
os.environ.setdefault('DATABASE_URL', 'postgresql://cecan_user:cecan_password@localhost:5432/cecan_db')

from sqlalchemy import create_engine, inspect

engine = create_engine(os.environ['DATABASE_URL'])
inspector = inspect(engine)

if 'scholar_paper_data' in inspector.get_table_names():
    print("✅ scholar_paper_data table EXISTS!")
    
    # Show columns
    columns = inspector.get_columns('scholar_paper_data')
    print(f"\nTable has {len(columns)} columns:")
    for col in columns:
        print(f"  - {col['name']}: {col['type']}")
else:
    print("❌ scholar_paper_data table DOES NOT EXIST!")
    print("\nTrying to create it manually...")
    
    from core.models import Base, ScholarPaperData
    Base.metadata.create_all(engine, tables=[ScholarPaperData.__table__])
    
    print("✅ Table created manually!")

print("\n🎉 All done! Scholar table is ready.")
