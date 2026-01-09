#!/usr/bin/env python3
"""
Fix orphaned researchers by recreating researcher_details
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def fix_orphaned_researchers():
    """Recreate researcher_details for orphaned researchers"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🔧 Fixing Orphaned Researchers")
        print("=" * 80)
        
        # Recreate researcher_details for academic_members that lost theirs
        print("\n📋 Recreating researcher_details for orphaned researchers...")
        sql = text("""
        INSERT INTO researcher_details (member_id, category)
        SELECT a.id, NULL
        FROM academic_members a
        WHERE a.member_type = 'researcher'
          AND NOT EXISTS (
            SELECT 1 FROM researcher_details r WHERE r.member_id = a.id
          );
        """)
        
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Recreated {result.rowcount} researcher_details")
        
        # Now mark them as inactive so they don't show
        print("\n📋 Marking duplicates as inactive...")
        sql = text("""
        UPDATE academic_members
        SET is_active = FALSE
        WHERE member_type = 'researcher'
          AND id IN (
            SELECT r.member_id
            FROM researcher_details r
            WHERE r.category IS NULL
          );
        """)
        
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Marked {result.rowcount} researchers as inactive")
        
        # Count active categorized researchers
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
              AND a.is_active = TRUE
              AND r.category IN ('Principal', 'Asociado', 'Adjunto');
        """))
        final_count = result.scalar()
        
        print("\n" + "=" * 80)
        print(f"✅ Fix completed!")
        print(f"   Active categorized researchers: {final_count}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_orphaned_researchers()
