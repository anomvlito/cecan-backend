#!/usr/bin/env python3
"""
Update Principal Investigators Script
Updates email, institution, and WP assignments for main researchers
"""
import sys
from pathlib import Path
from typing import List, Dict
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, WorkPackage, ResearcherDetails
from sqlalchemy.orm import joinedload

# Principal Investigators Data
PI_DATA = [
    {"wp": "1", "name": "Paula Margozzini", "email": "pmargozz@uc.cl", "institution": "UC"},
    {"wp": "1", "name": "Lorena Rodríguez", "email": "lorenarodriguez@uchile.cl", "institution": "UCh"},
    {"wp": "2", "name": "Bruno Nervi", "email": "bnervi@uc.cl", "institution": "UC"},
    {"wp": "2", "name": "Johanna Acevedo", "email": "johannaacevedo@udd.cl", "institution": "UDD"},
    {"wp": "3", "name": "Enrique Castellón", "email": "ecastell@med.uchile.cl", "institution": "UCh"},
    {"wp": "4", "name": "Oscar Arteaga", "email": "oarteaga@uchile.cl", "institution": "UCh"},
    {"wp": "4", "name": "Manuel Espinoza", "email": "manuel.espinoza@uc.cl", "institution": "UC"},
    {"wp": "5", "name": "Carla Taramasco", "email": "carla.taramasco@unab.cl", "institution": "UNAB"},
    {"wp": "PP", "name": "Carolina Goic", "email": "cgoicb@uc.cl", "institution": "UC"},
]

def find_best_match(target_name: str, candidates: List[AcademicMember]) -> tuple:
    """Find best matching researcher using fuzzy name matching"""
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        score = SequenceMatcher(None, 
                               candidate.full_name.lower().strip(), 
                               target_name.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    
    return best_match, best_score


def ensure_wp_exists(db, wp_name: str) -> WorkPackage:
    """Ensure Work Package exists, create if not"""
    wp = db.query(WorkPackage).filter(WorkPackage.name == wp_name).first()
    
    if not wp:
        print(f"  ✨ Creating new Work Package: {wp_name}")
        wp = WorkPackage(name=wp_name)
        db.add(wp)
        db.commit()
        db.refresh(wp)
    
    return wp


def update_principal_investigators(db):
    """Update PI data with emails, institutions, and WPs"""
    print("=" * 60)
    print("👥 Updating Principal Investigators")
    print("=" * 60)
    
    updated = 0
    created = 0
    not_found = 0
    
    # Get all researchers
    all_researchers = db.query(AcademicMember).filter(
        AcademicMember.member_type == 'researcher'
    ).all()
    
    for pi in PI_DATA:
        print(f"\n🔍 Processing: {pi['name']} (WP {pi['wp']})")
        
        # Ensure WP exists
        wp = ensure_wp_exists(db, f"WP{pi['wp']}")
        
        # Try exact match first
        researcher = db.query(AcademicMember).filter(
            AcademicMember.full_name.ilike(f"%{pi['name']}%")
        ).first()
        
        # If not found, use fuzzy matching
        if not researcher:
            match, score = find_best_match(pi['name'], all_researchers)
            if match and score > 0.80:  # 80% similarity threshold
                print(f"  🔗 Fuzzy match: '{pi['name']}' ≈ '{match.full_name}' ({score*100:.1f}%)")
                researcher = match
        
        if researcher:
            # Update existing researcher
            researcher.email = pi['email']
            researcher.institution = pi['institution']
            researcher.wp_id = wp.id
            
            # Also add to many-to-many relationship if not already there
            if wp not in researcher.wps:
                researcher.wps.append(wp)
            
            db.commit()
            print(f"  ✅ Updated: {researcher.full_name}")
            print(f"     Email: {pi['email']}")
            print(f"     Institution: {pi['institution']}")
            print(f"     WP: {wp.name}")
            updated += 1
        else:
            print(f"  ⚠️  NOT FOUND in database: {pi['name']}")
            print(f"     Creating new researcher...")
            
            # Create new researcher
            new_researcher = AcademicMember(
                full_name=pi['name'],
                email=pi['email'],
                institution=pi['institution'],
                member_type='researcher',
                wp_id=wp.id,
                is_active=True
            )
            db.add(new_researcher)
            db.flush()
            
            # Add to WP many-to-many
            new_researcher.wps.append(wp)
            
            db.commit()
            print(f"  ✨ Created new researcher: {pi['name']}")
            created += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Updated: {updated}")
    print(f"   ✨ Created: {created}")
    print(f"   ⚠️  Not Found: {not_found}")
    print("=" * 60)


def main():
    db = SessionLocal()
    try:
        update_principal_investigators(db)
        print("\n✅ Script completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
