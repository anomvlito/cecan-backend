#!/usr/bin/env python3
"""
Import CECAN Personnel to Database
Loads normalized Excel into academic_members with proper relationships
"""
import sys
import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, ResearcherDetails, StudentDetails, WorkPackage
import numpy as np

INPUT_FILE = "data/cecan_personnel_normalized.xlsx"

def safe_get(row, key):
    """Safely get value from row, converting NaN to None"""
    value = row.get(key)
    
    # Handle pandas NaN, numpy NaN, None, or string "NaN"
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, str) and value.strip().upper() in ['NAN', 'NONE', '']:
        return None
    
    return value

def find_tutor_by_name(db, tutor_name: str):
    """Find tutor by fuzzy name matching"""
    if not tutor_name or pd.isna(tutor_name) or tutor_name.strip() == "":
        return None
    
    # Try exact match first
    tutor = db.query(AcademicMember).filter(
        AcademicMember.full_name.ilike(f"%{tutor_name}%"),
        AcademicMember.member_type == 'researcher'
    ).first()
    
    if tutor:
        return tutor
    
    # Fuzzy matching
    all_researchers = db.query(AcademicMember).filter(
        AcademicMember.member_type == 'researcher'
    ).all()
    
    best_match = None
    best_score = 0
    
    for researcher in all_researchers:
        score = SequenceMatcher(None, 
                               researcher.full_name.lower().strip(),
                               tutor_name.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = researcher
    
    if best_match and best_score > 0.75:  # 75% similarity
        print(f"    🔗 Tutor match: '{tutor_name}' ≈ '{best_match.full_name}' ({best_score*100:.1f}%)")
        return best_match
    
    print(f"    ⚠️  Tutor not found: {tutor_name}")
    return None

def ensure_wp_exists(db, wp_name: str):
    """Ensure Work Package exists"""
    if not wp_name or pd.isna(wp_name):
        return None
    
    wp_name = f"WP{wp_name}"
    wp = db.query(WorkPackage).filter(WorkPackage.name == wp_name).first()
    
    if not wp:
        try:
            wp = WorkPackage(name=wp_name)
            db.add(wp)
            db.commit()  # Commit immediately to avoid sequence issues
            db.refresh(wp)
        except Exception as e:
            db.rollback()
            # Might already exist due to race condition, try fetching again
            wp = db.query(WorkPackage).filter(WorkPackage.name == wp_name).first()
            if not wp:
                raise e
    
    return wp

def import_personnel(db, dry_run=True):
    """Import personnel (researchers + staff)"""
    print("=" * 80)
    print("👥 Importing Personnel")
    print("=" * 80)
    
    df = pd.read_excel(INPUT_FILE, sheet_name='personnel')
    
    created = 0
    updated = 0
    skipped = 0
    
    for _, row in df.iterrows():
        full_name = row['full_name']
        email = row.get('email')
        
        if pd.isna(full_name) or not full_name:
            continue
        
        print(f"\n🔍 {full_name}")
        
        # Safely get values (converts NaN to None)
        email = safe_get(row, 'email')
        rut = safe_get(row, 'rut')
        institution = safe_get(row, 'institution')
        
        # Check if exists
        existing = None
        if email:
            existing = db.query(AcademicMember).filter(
                AcademicMember.email == email
            ).first()
        
        if not existing and rut:
            existing = db.query(AcademicMember).filter(
                AcademicMember.rut == rut
            ).first()
        
        # Get WP
        wp = ensure_wp_exists(db, safe_get(row, 'wp'))
        
        if existing:
            # Update
            existing.email = email if email else existing.email
            existing.institution = institution if institution else existing.institution
            existing.wp_id = wp.id if wp else existing.wp_id
            
            if wp and wp not in existing.wps:
                existing.wps.append(wp)
            
            if not dry_run:
                db.commit()
            
            print(f"  🔄 Updated existing")
            updated += 1
        else:
            # Create new
            new_member = AcademicMember(
                full_name=full_name,
                email=email,
                rut=rut,
                institution=institution,
                member_type=row['member_type'],
                wp_id=wp.id if wp else None,
                is_active=True
            )
            
            if not dry_run:
                db.add(new_member)
                db.flush()
                
                # Add to WP many-to-many
                if wp:
                    new_member.wps.append(wp)
                
                # Create ResearcherDetails if researcher
                if row['member_type'] == 'researcher':
                    details = ResearcherDetails(
                        member_id=new_member.id,
                        category=row.get('category')
                    )
                    db.add(details)
                
                db.commit()
            
            print(f"  ✅ Created (type: {row['member_type']}, category: {row.get('category')})")
            created += 1
    
    return {"created": created, "updated": updated, "skipped": skipped}

def import_students(db, dry_run=True):
    """Import students with tutor relationships"""
    print("\n" + "=" * 80)
    print("🎓 Importing Students")
    print("=" * 80)
    
    df = pd.read_excel(INPUT_FILE, sheet_name='students')
    
    created = 0
    updated = 0
    no_tutor = 0
    
    for _, row in df.iterrows():
        full_name = row['full_name']
        email = row.get('email')
        
        if pd.isna(full_name) or not full_name:
            continue
        
        print(f"\n🔍 {full_name}")
        
        # Safely get values
        email = safe_get(row, 'email')
        rut = safe_get(row, 'rut')
        university = safe_get(row, 'university')
        
        # Check if exists
        existing = None
        if email:
            existing = db.query(AcademicMember).filter(
                AcademicMember.email == email
            ).first()
        
        # Find tutor
        tutor = find_tutor_by_name(db, safe_get(row, 'tutor_name'))
        co_tutor = find_tutor_by_name(db, safe_get(row, 'co_tutor_name'))
        
        if not tutor:
            no_tutor += 1
        
        # Get WP
        wp = ensure_wp_exists(db, safe_get(row, 'wp'))
        
        if existing:
            # Update student details
            if existing.student_details:
                existing.student_details.tutor_id = tutor.id if tutor else None
                existing.student_details.co_tutor_id = co_tutor.id if co_tutor else None
                existing.student_details.thesis_title = row.get('thesis_title')
                existing.student_details.program = row.get('program')
                existing.student_details.university = row.get('university')
            
            if not dry_run:
                db.commit()
            
            print(f"  🔄 Updated")
            updated += 1
        else:
            # Create new student
            new_student = AcademicMember(
                full_name=full_name,
                email=email,
                rut=rut,
                institution=university,
                member_type='student',
                wp_id=wp.id if wp else None,
                is_active=True
            )
            
            if not dry_run:
                db.add(new_student)
                db.flush()
                
                # Create StudentDetails
                details = StudentDetails(
                    member_id=new_student.id,
                    tutor_id=tutor.id if tutor else None,
                    co_tutor_id=co_tutor.id if co_tutor else None,
                    thesis_title=row.get('thesis_title'),
                    program=row.get('program'),
                    university=row.get('university')
                )
                db.add(details)
                
                # Add to WP
                if wp:
                    new_student.wps.append(wp)
                
                db.commit()
            
            print(f"  ✅ Created (Tutor: {tutor.full_name if tutor else 'None'})")
            created += 1
    
    return {"created": created, "updated": updated, "no_tutor": no_tutor}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Import CECAN personnel")
    parser.add_argument("--auto-create", action="store_true", help="Actually create records (not dry-run)")
    args = parser.parse_args()
    
    dry_run = not args.auto_create
    
    print("\n🚀 CECAN Personnel Import Script")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (Preview)' if dry_run else 'PRODUCTION (Creating)'}")
    print("=" * 80)
    
    db = SessionLocal()
    
    try:
        # Step 1: Import personnel
        result_personnel = import_personnel(db, dry_run)
        
        # Step 2: Import students
        result_students = import_students(db, dry_run)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Import Summary")
        print("=" * 80)
        print(f"Personnel:")
        print(f"  ✅ Created: {result_personnel['created']}")
        print(f"  🔄 Updated: {result_personnel['updated']}")
        print(f"\nStudents:")
        print(f"  ✅ Created: {result_students['created']}")
        print(f"  🔄 Updated: {result_students['updated']}")
        print(f"  ⚠️  No Tutor: {result_students['no_tutor']}")
        
        if dry_run:
            print("\n🔍 This was a DRY RUN. Use --auto-create to actually import.")
        else:
            print("\n✅ Import completed successfully!")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
