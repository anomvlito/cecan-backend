import sys
import os
import json
from sqlalchemy.orm import joinedload

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import get_session, AcademicMember, WorkPackage

def verify_members_wps():
    print("Verifying Members WPs...")
    db = get_session()
    try:
        # Simulate the query used in the endpoint
        members = db.query(AcademicMember).options(joinedload(AcademicMember.wps)).limit(5).all()
        
        print(f"Fetched {len(members)} members.")
        
        for member in members:
            print(f"\nMember: {member.full_name} (ID: {member.id})")
            print(f"Legacy WP ID: {member.wp_id}")
            
            # Check the wps relationship
            wps = member.wps
            print(f"WPs Count: {len(wps)}")
            
            wps_data = [{"id": wp.id, "nombre": wp.nombre} for wp in wps]
            print(f"WPs Data: {json.dumps(wps_data, ensure_ascii=False)}")
            
            if not wps and member.wp_id:
                print("WARNING: Member has legacy wp_id but no WPs in new relationship (might be expected if sync only handled researchers)")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_members_wps()
