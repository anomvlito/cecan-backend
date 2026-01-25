#!/usr/bin/env python3
"""
Audit CECAN Personnel Import
Check what was actually imported
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def audit_personnel():
    """Audit imported personnel"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("📊 CECAN Personnel Audit")
        print("=" * 80)
        
        # Count by type
        result = db.execute(text("""
            SELECT member_type, COUNT(*) as count
            FROM academic_members
            GROUP BY member_type
            ORDER BY member_type;
        """))
        
        print("\n📈 By Type:")
        for row in result:
            print(f"   {row[0]}: {row[1]}")
        
        # Researchers by category
        result = db.execute(text("""
            SELECT r.category, COUNT(*) as count
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
            GROUP BY r.category
            ORDER BY r.category;
        """))
        
        print("\n🔬 Researchers by Category:")
        for row in result:
            print(f"   {row[0] or 'N/A'}: {row[1]}")
        
        # Students with/without tutors
        result = db.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE s.tutor_id IS NOT NULL) as with_tutor,
                COUNT(*) FILTER (WHERE s.tutor_id IS NULL) as without_tutor
            FROM academic_members a
            JOIN student_details s ON a.id = s.member_id
            WHERE a.member_type = 'student';
        """))
        
        row = result.fetchone()
        print("\n🎓 Students:")
        print(f"   With Tutor: {row[0]}")
        print(f"   Without Tutor: {row[1]}")
        
        # Sample researchers
        result = db.execute(text("""
            SELECT a.full_name, a.email, r.category
            FROM academic_members a
            LEFT JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
            ORDER BY a.id DESC
            LIMIT 10;
        """))
        
        print("\n👥 Recent Researchers (last 10):")
        for row in result:
            print(f"   {row[0]} ({row[2] or 'N/A'}) - {row[1] or 'no email'}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    audit_personnel()
