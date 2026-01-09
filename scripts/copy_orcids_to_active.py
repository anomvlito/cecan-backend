#!/usr/bin/env python3
"""
Copy ORCIDs from inactive to active researchers with same name
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def copy_orcids():
    """Copy ORCIDs from inactive to active researchers"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("📋 Copying ORCIDs to Active Researchers")
        print("=" * 80)
        
        # Copy ORCIDs from inactive researchers to active ones with same name
        sql = text("""
        UPDATE researcher_details r_active
        SET 
            orcid = r_inactive.orcid,
            indice_h = COALESCE(r_active.indice_h, r_inactive.indice_h),
            citaciones_totales = COALESCE(r_active.citaciones_totales, r_inactive.citaciones_totales),
            works_count = COALESCE(r_active.works_count, r_inactive.works_count),
            i10_index = COALESCE(r_active.i10_index, r_inactive.i10_index)
        FROM researcher_details r_inactive
        JOIN academic_members a_inactive ON r_inactive.member_id = a_inactive.id
        JOIN academic_members a_active ON LOWER(TRIM(a_active.full_name)) = LOWER(TRIM(a_inactive.full_name))
        WHERE r_active.member_id = a_active.id
          AND a_active.is_active = TRUE
          AND a_inactive.is_active = FALSE
          AND r_inactive.orcid IS NOT NULL
          AND r_active.orcid IS NULL
          AND r_active.category IN ('Principal', 'Asociado', 'Adjunto');
        """)
        
        result = db.execute(sql)
        db.commit()
        
        print(f"\n✅ Copied ORCIDs to {result.rowcount} active researchers")
        
        # Count researchers with ORCID
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
              AND a.is_active = TRUE
              AND r.category IN ('Principal', 'Asociado', 'Adjunto')
              AND r.orcid IS NOT NULL;
        """))
        with_orcid = result.scalar()
        
        print(f"   Active researchers with ORCID: {with_orcid}/105")
        
        print("\n" + "=" * 80)
        print("✅ ORCIDs copied successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    copy_orcids()
