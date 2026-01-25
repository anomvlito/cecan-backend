#!/usr/bin/env python3
"""
Test Members Endpoint
Direct test to see if filtered researchers return correctly
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, ResearcherDetails, MemberType
from sqlalchemy.orm import joinedload

def test_researcher_query():
    """Test the exact query used in the endpoint"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("🧪 Testing Researcher Query")
        print("=" * 80)
        
        # Exact same query as endpoint
        query = db.query(AcademicMember).options(
            joinedload(AcademicMember.wps),
            joinedload(AcademicMember.researcher_details)
        )
        
        query = query.filter(AcademicMember.member_type == MemberType.RESEARCHER)
        query = query.join(ResearcherDetails).filter(
            ResearcherDetails.category.in_(['Principal', 'Asociado', 'Adjunto'])
        )
        
        results = query.limit(10).all()
        
        print(f"\n📊 Query returned {len(results)} results (showing first 10)")
        print("=" * 80)
        
        for member in results:
            wp_names = [wp.name for wp in member.wps] if member.wps else []
            category = member.researcher_details.category if member.researcher_details else "N/A"
            
            print(f"\n👤 {member.full_name}")
            print(f"   Email: {member.email or 'N/A'}")
            print(f"   RUT: {member.rut or 'N/A'}")
            print(f"   Category: {category}")
            print(f"   WPs: {', '.join(wp_names) if wp_names else 'None'}")
        
        # Count total
        total = query.count()
        print("\n" + "=" * 80)
        print(f"✅ Total researchers with category: {total}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_researcher_query()
