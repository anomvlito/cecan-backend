#!/usr/bin/env python3
"""
Diagnose ORCID status
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def diagnose_orcids():
    """Check ORCID status"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🔍 ORCID Diagnosis")
        print("=" * 80)
        
        # Count active researchers with ORCID
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.is_active = TRUE
              AND r.orcid IS NOT NULL;
        """))
        print(f"\nActive researchers with ORCID: {result.scalar()}")
        
        # Count inactive researchers with ORCID
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.is_active = FALSE
              AND r.orcid IS NOT NULL;
        """))
        print(f"Inactive researchers with ORCID: {result.scalar()}")
        
        # Sample inactive researchers
        result = db.execute(text("""
            SELECT a.full_name, r.orcid, r.category
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.is_active = FALSE
              AND r.orcid IS NOT NULL
            LIMIT 10;
        """))
        
        print("\n📋 Sample inactive with ORCID:")
        for row in result:
            print(f"   {row[0]} - {row[1]} ({row[2] or 'N/A'})")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_orcids()
