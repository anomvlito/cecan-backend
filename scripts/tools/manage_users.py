import sys
import os
from sqlalchemy.orm import Session

# Add current directory to path so imports work
sys.path.append(os.getcwd())

from database.session import get_session
from core.models import User, UserRole
from utils.security import get_password_hash

def list_users(db: Session):
    print("\n--- 👥 EXISTING USERS ---")
    users = db.query(User).all()
    if not users:
        print("   (No users found in database)")
    for u in users:
        status = "Active" if u.is_active else "Inactive"
        print(f"   ID: {u.id} | Email: {u.email} | Role: {u.role.value} | Status: {status}")
    print("-------------------------\n")

def create_admin(db: Session, email, password):
    print(f"Processing Admin User: {email}...")
    
    # Check if exists
    existing = db.query(User).filter(User.email == email).first()
    
    if existing:
        print(f"🔄 User {email} already exists. Updating password...")
        try:
            existing.hashed_password = get_password_hash(password)
            existing.is_active = True
            existing.role = UserRole.ADMIN
            db.commit()
            print(f"✅ SUCCESS: Password updated for {email}.")
        except Exception as e:
            print(f"❌ Error updating user: {e}")
            db.rollback()
    else:
        print(f"🆕 Creating new user {email}...")
        try:
            new_user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name="System Admin",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(new_user)
            db.commit()
            print(f"✅ SUCCESS: User {email} created with ADMIN privileges.")
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            db.rollback()

def main():
    db = get_session()
    
    try:
        # Check connection by listing users first
        list_users(db)
        
        # Simple interactive mode if arguments provided
        if len(sys.argv) == 3:
            email = sys.argv[1]
            password = sys.argv[2]
            create_admin(db, email, password)
            list_users(db) # Show update
        else:
            print("Usage to create user: python manage_users.py <email> <password>")
            
    except Exception as e:
        print(f"❌ CRITICAL DATABASE ERROR: {e}")
        print("Check your DATABASE_URL and connection.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
