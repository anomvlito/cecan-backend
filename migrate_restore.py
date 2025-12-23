
import sqlite3
import os
from database.session import DB_PATH

def migrate():
    print(f"Checking database at: {DB_PATH}")
    
    # Ensure we use the absolute path if DB_PATH is relative
    
    # Force use of local cecan.db in the same directory as this script (backend/)
    # This fixes the issue where it connects to an empty DB in the root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "cecan.db")
        
    print(f"Target DB: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # columns to add
    columns = [
        ("doi_verification_status", "VARCHAR(50) DEFAULT 'pending'"),
        ("has_funding_ack", "BOOLEAN DEFAULT 0"),
        ("anid_report_status", "VARCHAR(50) DEFAULT 'Pending'"),
        ("canonical_doi", "VARCHAR(100)"),
        ("metrics_last_updated", "DATETIME"),
        ("metrics_data", "JSON")
    ]
    
    
    # Check for table existence (case-insensitive)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    print(f"Found tables: {tables}")
    
    table = "publicaciones"
    if "Publicaciones" in tables:
        table = "Publicaciones"
    elif "publicaciones" not in tables:
        print(f"❌ Table 'publicaciones' not found in {db_path}")
        return
        
    print(f"Targeting table: {table}")
    
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
