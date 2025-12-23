
import sqlite3
import os
from database.session import DB_PATH

def migrate():
    print(f"Checking database at: {DB_PATH}")
    
    # Ensure we use the absolute path if DB_PATH is relative
    if not os.path.isabs(DB_PATH):
        # Assuming run from backend/ dir
        db_path = os.path.abspath(DB_PATH)
    else:
        db_path = DB_PATH
        
    print(f"Target DB: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # columns to add
    columns = [
        ("doi_verification_status", "VARCHAR(50) DEFAULT 'pending'"),
        ("has_funding_ack", "BOOLEAN DEFAULT 0"),
        ("anid_report_status", "VARCHAR(50) DEFAULT 'Pending'"),
        ("canonical_doi", "VARCHAR(100)")
    ]
    
    table = "publicaciones"
    
    try:
        # Get existing columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        
        for col_name, col_def in columns:
            if col_name not in existing:
                print(f"Adding column: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    print(f"✅ Added {col_name}")
                except Exception as e:
                    print(f"❌ Failed to add {col_name}: {e}")
            else:
                print(f"ℹ️ Column {col_name} already exists.")
                
        conn.commit()
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
