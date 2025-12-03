import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.database.session import get_session
from backend.core.models import User
from sqlalchemy import text

def check_db():
    print("Checking database connection...")
    try:
        db = get_session()
        # Test connection
        db.execute(text("SELECT 1"))
        print("Database connection successful.")
        
        # Check if users table exists
        print("Checking for users table...")
        try:
            users = db.query(User).all()
            print(f"Found {len(users)} users.")
            for user in users:
                print(f" - {user.email} ({user.role})")
        except Exception as e:
            print(f"Error querying users: {e}")
            print("Tables might be missing.")
            
        db.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    check_db()
