#!/usr/bin/env python3
"""
Detailed Audit of ORCID consistency
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def audit_orcid_consistency():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("🔍 ORCID Data Consistency Audit")
        print("=" * 80)
        
        # 1. Total Active Researchers with Categories
        print("\n📊 Universe: Active Researchers (Principal/Asociado/Adjunto)")
        
        sql_universe = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN r.orcid IS NOT NULL AND r.orcid != '' THEN 1 ELSE 0 END) as with_orcid,
                SUM(CASE WHEN r.orcid IS NULL OR r.orcid = '' THEN 1 ELSE 0 END) as without_orcid
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
              AND a.is_active = TRUE
              AND r.category IN ('Principal', 'Asociado', 'Adjunto');
        """)
        stats = db.execute(sql_universe).fetchone()
        
        print(f"   Total: {stats.total}")
        print(f"   ✅ With ORCID:    {stats.with_orcid} ({(stats.with_orcid/stats.total*100):.1f}%)")
        print(f"   ⚠️  Without ORCID: {stats.without_orcid} ({(stats.without_orcid/stats.total*100):.1f}%)")
        
        # 2. List those WITHOUT ORCID to see if they should have one
        if stats.without_orcid > 0:
            print(f"\n📋 Researchers MISSING ORCID ({stats.without_orcid}):")
            print(f"{'ID':<5} {'Name':<40} {'Category':<15} {'WP':<5}")
            print("-" * 70)
            
            sql_missing = text("""
                SELECT a.id, a.full_name, r.category, a.wp_id
                FROM academic_members a
                JOIN researcher_details r ON a.id = r.member_id
                WHERE a.member_type = 'researcher'
                  AND a.is_active = TRUE
                  AND r.category IN ('Principal', 'Asociado', 'Adjunto')
                  AND (r.orcid IS NULL OR r.orcid = '')
                ORDER BY a.full_name;
            """)
            missing = db.execute(sql_missing).fetchall()
            
            for row in missing:
                wp = str(row.wp_id) if row.wp_id else "-"
                print(f"{row.id:<5} {row.full_name[:38]:<40} {row.category:<15} {wp:<5}")
            
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    audit_orcid_consistency()
