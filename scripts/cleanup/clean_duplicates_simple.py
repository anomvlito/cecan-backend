#!/usr/bin/env python3
"""
Delete duplicate researchers - keep only categorized ones
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def clean_duplicates():
    """Delete all researchers without category that have duplicates"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🧹 Cleaning Duplicate Researchers")
        print("=" * 80)
        
        # Just delete all researchers without proper category
        print("\n📋 Step 1: Deleting researcher_details without category...")
        sql = text("""
        DELETE FROM researcher_details r
        WHERE r.category IS NULL 
           OR r.category NOT IN ('Principal', 'Asociado', 'Adjunto');
        """)
        
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Deleted {result.rowcount} researcher_details")
        
        print("\n📋 Step 2: Deleting academic_members without researcher_details...")
        sql = text("""
        DELETE FROM academic_members a
        WHERE a.member_type = 'researcher'
          AND NOT EXISTS (
            SELECT 1 FROM researcher_details r WHERE r.member_id = a.id
          );
        """)
        
        result = db.execute(sql)
        db.commit()
        deleted = result.rowcount
        
        print(f"   ✅ Deleted {deleted} uncategorized researchers")
        
        # Count remaining
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
              AND r.category IN ('Principal', 'Asociado', 'Adjunto');
        """))
        final_count = result.scalar()
        
        print("\n" + "=" * 80)
        print(f"✅ Cleanup completed!")
        print(f"   Remaining categorized researchers: {final_count}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_duplicates()
