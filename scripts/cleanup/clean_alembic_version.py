#!/usr/bin/env python3
"""
Clean Alembic version table
Removes orphaned migration reference
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def clean_alembic_version():
    """Remove orphaned d4e5f6a7b8c9 from alembic_version"""
    db = SessionLocal()
    
    try:
        print("🔧 Cleaning alembic_version table...")
        
        # Remove the orphaned revision
        sql = text("DELETE FROM alembic_version WHERE version_num = 'd4e5f6a7b8c9';")
        db.execute(sql)
        db.commit()
        
        print("✅ Orphaned migration removed from DB")
        
        # Show current version
        result = db.execute(text("SELECT * FROM alembic_version;"))
        current = result.fetchall()
        print(f"Current DB version: {current}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_alembic_version()
