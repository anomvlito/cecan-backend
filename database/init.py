from core.models import create_all_tables, drop_all_tables
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        print("Resetting database...")
        drop_all_tables()
    
    create_all_tables()
    print("Database initialized successfully.")
