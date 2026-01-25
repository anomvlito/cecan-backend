#!/usr/bin/env python3
"""
Fix Work Packages Sequence
Resets PostgreSQL sequence to avoid duplicate key errors
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def fix_wp_sequence():
    """Reset work_packages sequence to max ID + 1"""
    db = SessionLocal()
    
    try:
        print("🔧 Fixing work_packages sequence...")
        
        # Reset sequence to max ID
        sql = text("""
        SELECT setval('work_packages_id_seq', 
                     (SELECT COALESCE(MAX(id), 0) + 1 FROM work_packages), 
                     false);
        """)
        
        db.execute(sql)
        db.commit()
        
        print("✅ Sequence fixed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_wp_sequence()
