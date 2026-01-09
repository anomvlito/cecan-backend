#!/usr/bin/env python3
"""
Merge Duplicate Researchers
Combines ORCID data with Excel data
"""
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, ResearcherDetails
from sqlalchemy import and_, text

def similarity(a, b):
    """Calculate name similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def merge_duplicates(dry_run=True):
    """Merge duplicate researchers"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🔄 Merging Duplicate Researchers")
        print(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
        print("=" * 80)
        
        # Get all researchers
        all_researchers = db.query(AcademicMember).filter(
            AcademicMember.member_type == 'researcher'
        ).all()
        
        merged = 0
        deleted = 0
        
        # Find duplicates by name similarity
        for i, r1 in enumerate(all_researchers):
            if not r1:  # Skip if already processed
                continue
                
            for j, r2 in enumerate(all_researchers[i+1:], start=i+1):
                if not r2:  # Skip if already processed
                    continue
                
                # Check similarity
                sim = similarity(r1.full_name, r2.full_name)
                
                if sim > 0.80:  # 80% similar
                    print(f"\n🔍 Potential duplicate (similarity: {sim*100:.1f}%):")
                    print(f"   [{r1.id}] {r1.full_name}")
                    print(f"       Email: {r1.email or 'N/A'}, Category: {r1.researcher_details.category if r1.researcher_details else 'N/A'}, ORCID: {r1.researcher_details.orcid if r1.researcher_details else 'N/A'}")
                    print(f"   [{r2.id}] {r2.full_name}")
                    print(f"       Email: {r2.email or 'N/A'}, Category: {r2.researcher_details.category if r2.researcher_details else 'N/A'}, ORCID: {r2.researcher_details.orcid if r2.researcher_details else 'N/A'}")
                    
                    # Decide which to keep (prefer one with category)
                    primary = r2 if (r2.researcher_details and r2.researcher_details.category) else r1
                    secondary = r1 if primary == r2 else r2
                    
                    print(f"\n   → Keeping: [{primary.id}] {primary.full_name}")
                    print(f"   → Merging from: [{secondary.id}] {secondary.full_name}")
                    
                    if not dry_run:
                        # Ensure both have researcher_details
                        if not primary.researcher_details:
                            primary.researcher_details = ResearcherDetails(member_id=primary.id)
                            db.add(primary.researcher_details)
                            db.flush()
                        
                        if not secondary.researcher_details:
                            secondary.researcher_details = ResearcherDetails(member_id=secondary.id)
                            db.add(secondary.researcher_details)
                            db.flush()
                        
                        # Merge data (take non-null values)
                        if secondary.researcher_details.orcid and not primary.researcher_details.orcid:
                            primary.researcher_details.orcid = secondary.researcher_details.orcid
                            print(f"      ✅ Copied ORCID: {secondary.researcher_details.orcid}")
                        
                        if secondary.researcher_details.indice_h and not primary.researcher_details.indice_h:
                            primary.researcher_details.indice_h = secondary.researcher_details.indice_h
                            print(f"      ✅ Copied H-Index: {secondary.researcher_details.indice_h}")
                        
                        if secondary.researcher_details.citaciones_totales and not primary.researcher_details.citaciones_totales:
                            primary.researcher_details.citaciones_totales = secondary.researcher_details.citaciones_totales
                            print(f"      ✅ Copied Citations: {secondary.researcher_details.citaciones_totales}")
                        
                        if secondary.researcher_details.works_count and not primary.researcher_details.works_count:
                            primary.researcher_details.works_count = secondary.researcher_details.works_count
                            print(f"      ✅ Copied Works: {secondary.researcher_details.works_count}")
                        
                        if secondary.researcher_details.i10_index and not primary.researcher_details.i10_index:
                            primary.researcher_details.i10_index = secondary.researcher_details.i10_index
                            print(f"      ✅ Copied i10: {secondary.researcher_details.i10_index}")
                        
                        # Copy email if missing
                        if secondary.email and not primary.email:
                            primary.email = secondary.email
                            print(f"      ✅ Copied Email: {secondary.email}")
                        
                        # Update all foreign key references BEFORE deleting
                        # Update project_researchers
                        db.execute(text("""
                            UPDATE project_researchers 
                            SET member_id = :primary_id 
                            WHERE member_id = :secondary_id
                        """), {"primary_id": primary.id, "secondary_id": secondary.id})
                        
                        # Update student tutors/co-tutors
                        db.execute(text("""
                            UPDATE student_details 
                            SET tutor_id = :primary_id 
                            WHERE tutor_id = :secondary_id
                        """), {"primary_id": primary.id, "secondary_id": secondary.id})
                        
                        db.execute(text("""
                            UPDATE student_details 
                            SET co_tutor_id = :primary_id 
                            WHERE co_tutor_id = :secondary_id
                        """), {"primary_id": primary.id, "secondary_id": secondary.id})
                        
                        # Clear ORCID from secondary to avoid unique constraint violation
                        if secondary.researcher_details and secondary.researcher_details.orcid:
                            secondary.researcher_details.orcid = None
                            secondary.researcher_details.indice_h = None
                            secondary.researcher_details.citaciones_totales = None
                            secondary.researcher_details.works_count = None
                            secondary.researcher_details.i10_index = None
                            db.flush()
                        
                        # Delete secondary
                        db.delete(secondary)
                        all_researchers[j] = None  # Mark as processed
                        
                        db.commit()
                        deleted += 1
                    
                    merged += 1
                    print("   ✅ Merged")
        
        print("\n" + "=" * 80)
        print(f"📊 Summary:")
        print(f"   Duplicates found: {merged}")
        print(f"   Records deleted: {deleted}")
        
        if dry_run:
            print("\n🔍 This was a DRY RUN. Use --execute to actually merge.")
        else:
            print("\n✅ Merge completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually merge (not dry-run)")
    args = parser.parse_args()
    
    merge_duplicates(dry_run=not args.execute)
