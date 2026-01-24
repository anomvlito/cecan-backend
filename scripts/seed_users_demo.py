
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database.session import get_session
from core.models import User, UserRole, AcademicMember, MemberType, WorkPackage, ResearcherDetails
from services.auth_service import AuthService

def seed_demo_users():
    """Create demo users for each role linked to academic members."""
    db = get_session()
    auth_service = AuthService(db)
    
    print("\n=== Seeding Demo Users & Members ===\n")
    
    # 0. Ensure WP exists
    wp1 = db.query(WorkPackage).filter_by(id=1).first()
    if not wp1:
        wp1 = WorkPackage(id=1, name="WP1 - Prevention & Reduction")
        db.add(wp1)
        db.commit()
    
    demos = [
        {
            "email": "pi@cecan.cl",
            "password": "pi123",
            "role": "pi",  # Explicit lowercase string
            "name": "Dr. Gregory House",
            "member_type": "researcher", # Explicit string
            "category": "Principal"
        },
        {
            "email": "researcher@cecan.cl",
            "password": "res123",
            "role": "researcher",
            "name": "Dr. James Wilson",
            "member_type": "researcher",
            "category": "Asociado"
        },
        {
            "email": "student@cecan.cl",
            "password": "stu123",
            "role": "student",
            "name": "Eric Foreman",
            "member_type": "student",
            "category": None
        },
        {
            "email": "staff@cecan.cl",
            "password": "staff123",
            "role": "staff",
            "name": "Lisa Cuddy",
            "member_type": "staff",
            "category": None
        },
        {
            "email": "viewer@cecan.cl",
            "password": "view123",
            "role": "viewer",
            "name": "Visitor Guest",
            "member_type": "researcher", 
            "category": "Adjunto"
        }
    ]
    
    count = 0
    for demo in demos:
        # Check if user exists
        existing_user = db.query(User).filter_by(email=demo["email"]).first()
        if existing_user:
            print(f"⚠️  User {demo['email']} already exists. Skipping.")
            continue
            
        print(f"Creating {demo['role']} user: {demo['email']}...")
        print(f"DEBUG: role value being sent is '{demo['role']}'")

        # 1. Create Academic Member
        member = AcademicMember(
            full_name=demo["name"],
            email=demo["email"],
            member_type=demo["member_type"],
            wp_id=1,
            institution="Hospital Princeton"
        )
        db.add(member)
        db.flush() # get ID
        
        # 2. Add ResearcherDetails if applicable
        if demo["member_type"] == "researcher":
            details = ResearcherDetails(
                member_id=member.id,
                category=demo["category"],
                is_auditable=True
            )
            db.add(details)
        
        # 3. Create User linked to Member
        user = auth_service.create_user(
            email=demo["email"],
            password=demo["password"],
            full_name=demo["name"],
            role=demo["role"]
        )
        
        count += 1
        print(f"  ✓ Created user and member for {demo['name']}")
        
    db.commit()
    print(f"\n✅ Created {count} demo users.")
    print("Passwords are: pi123, res123, stu123, staff123, view123")

if __name__ == "__main__":
    seed_demo_users()
