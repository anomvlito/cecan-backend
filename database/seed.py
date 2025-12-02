from database.session import get_session
from services.auth_service import AuthService
from core.models import UserRole

def seed_users():
    db = get_session()
    auth_service = AuthService(db)
    
    email = "admin@cecan.cl"
    password = "admin123"
    
    try:
        user = auth_service.get_user_by_email(email)
        if not user:
            print(f"Creating admin user: {email}")
            auth_service.create_user(
                email=email,
                password=password,
                full_name="Admin Cecan",
                role=UserRole.ADMIN
            )
            print("Admin user created successfully.")
        else:
            print("Admin user already exists.")
    except Exception as e:
        print(f"Error seeding users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
