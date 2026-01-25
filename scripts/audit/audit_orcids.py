#!/usr/bin/env python3
"""
Audit ORCIDs - Check status
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def audit_orcids():
    """Check ORCID status"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🔍 ORCID Audit")
        print("=" * 80)
        
        # Count researchers with ORCID
        result = db.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE r.orcid IS NOT NULL AND r.orcid != '') as with_orcid,
                COUNT(*) FILTER (WHERE r.orcid IS NULL OR r.orcid = '') as without_orcid
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher';
        """))
        
        row = result.fetchone()
        print(f"\n📊 Researchers:")
        print(f"   With ORCID: {row[0]}")
        print(f"   Without ORCID: {row[1]}")
        
        # Sample ORCIDs
        result = db.execute(text("""
            SELECT a.full_name, r.orcid, r.category
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher' 
            AND r.orcid IS NOT NULL 
            AND r.orcid != ''
            LIMIT 10;
        """))
        
        print(f"\n✅ Sample with ORCID:")
        for row in result:
            print(f"   {row[0]} ({row[2]}) - {row[1]}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    audit_orcids()
