#!/usr/bin/env python3
"""
Simple SQL-based duplicate merge
Keeps categorized researchers, copies ORCIDs, deletes duplicates
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def merge_duplicates_sql():
    """Merge duplicates using direct SQL"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🔄 Merging Duplicate Researchers (SQL)")
        print("=" * 80)
        
        # Step 1: Update ORCIDs on categorized researchers from their duplicates
        print("\n📋 Step 1: Copying ORCIDs to categorized researchers...")
        sql = text("""
        WITH duplicates AS (
            SELECT 
                a1.id as keep_id,
                a2.id as remove_id,
                r2.orcid,
                r2.indice_h,
                r2.citaciones_totales,
                r2.works_count,
                r2.i10_index
            FROM academic_members a1
            JOIN researcher_details r1 ON a1.id = r1.member_id
            JOIN academic_members a2 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            JOIN researcher_details r2 ON a2.id = r2.member_id
            WHERE a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
              AND (r2.category IS NULL OR r2.category NOT IN ('Principal', 'Asociado', 'Adjunto'))
              AND r2.orcid IS NOT NULL
              AND r1.orcid IS NULL
        )
        UPDATE researcher_details r
        SET 
            orcid = d.orcid,
            indice_h = COALESCE(r.indice_h, d.indice_h),
            citaciones_totales = COALESCE(r.citaciones_totales, d.citaciones_totales),
            works_count = COALESCE(r.works_count, d.works_count),
            i10_index = COALESCE(r.i10_index, d.i10_index)
        FROM duplicates d
        WHERE r.member_id = d.keep_id;
        """)
        
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Updated {result.rowcount} researchers with ORCID data")
        
        # Step 2: Update foreign key references
        print("\n📋 Step 2: Updating foreign key references...")
        
        # Update project_researchers
        sql = text("""
        UPDATE project_researchers pr
        SET member_id = (
            SELECT a1.id
            FROM academic_members a1
            JOIN researcher_details r1 ON a1.id = r1.member_id
            JOIN academic_members a2 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            WHERE a2.id = pr.member_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM academic_members a2
            JOIN academic_members a1 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            JOIN researcher_details r1 ON a1.id = r1.member_id
            WHERE a2.id = pr.member_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
        );
        """)
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Updated {result.rowcount} project_researchers")
        
        # Update student tutors
        sql = text("""
        UPDATE student_details sd
        SET tutor_id = (
            SELECT a1.id
            FROM academic_members a1
            JOIN researcher_details r1 ON a1.id = r1.member_id
            JOIN academic_members a2 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            WHERE a2.id = sd.tutor_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
            LIMIT 1
        )
        WHERE tutor_id IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM academic_members a2
            JOIN academic_members a1 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            JOIN researcher_details r1 ON a1.id = r1.member_id
            WHERE a2.id = sd.tutor_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
        );
        """)
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Updated {result.rowcount} student tutors")
        
        # Update student co-tutors
        sql = text("""
        UPDATE student_details sd
        SET co_tutor_id = (
            SELECT a1.id
            FROM academic_members a1
            JOIN researcher_details r1 ON a1.id = r1.member_id
            JOIN academic_members a2 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            WHERE a2.id = sd.co_tutor_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
            LIMIT 1
        )
        WHERE co_tutor_id IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM academic_members a2
            JOIN academic_members a1 ON LOWER(TRIM(a1.full_name)) = LOWER(TRIM(a2.full_name))
            JOIN researcher_details r1 ON a1.id = r1.member_id
            WHERE a2.id = sd.co_tutor_id
              AND a1.id != a2.id
              AND r1.category IN ('Principal', 'Asociado', 'Adjunto')
        );
        """)
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Updated {result.rowcount} student co-tutors")
        
        # Step 3: Delete duplicates without category
        print("\n📋 Step 3: Deleting uncategorized duplicates...")
        sql = text("""
        DELETE FROM academic_members a
        WHERE a.member_type = 'researcher'
          AND EXISTS (
            SELECT 1
            FROM researcher_details r
            WHERE r.member_id = a.id
              AND (r.category IS NULL OR r.category NOT IN ('Principal', 'Asociado', 'Adjunto'))
          )
          AND EXISTS (
            SELECT 1
            FROM academic_members a2
            JOIN researcher_details r2 ON a2.id = r2.member_id
            WHERE LOWER(TRIM(a.full_name)) = LOWER(TRIM(a2.full_name))
              AND a.id != a2.id
              AND r2.category IN ('Principal', 'Asociado', 'Adjunto')
          );
        """)
        result = db.execute(sql)
        db.commit()
        print(f"   ✅ Deleted {result.rowcount} duplicate researchers")
        
        # Step 4: Count final researchers
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM academic_members a
            JOIN researcher_details r ON a.id = r.member_id
            WHERE a.member_type = 'researcher'
              AND r.category IN ('Principal', 'Asociado', 'Adjunto');
        """))
        final_count = result.scalar()
        
        print("\n" + "=" * 80)
        print(f"✅ Merge completed!")
        print(f"   Final researcher count: {final_count}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    merge_duplicates_sql()
