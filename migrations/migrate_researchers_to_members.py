import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

def migrate_researchers():
    print("Starting migration: Investigadores (Legacy) -> AcademicMember (New)...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Get all legacy researchers
        cursor.execute("SELECT id, nombre FROM Investigadores")
        legacy_researchers = cursor.fetchall()
        print(f"Found {len(legacy_researchers)} legacy researchers.")
        
        migrated_count = 0
        
        for row in legacy_researchers:
            name = row['nombre']
            
            # Check if already exists in academic_members
            cursor.execute("SELECT id FROM academic_members WHERE full_name = ?", (name,))
            exists = cursor.fetchone()
            
            if not exists:
                # Insert into academic_members
                cursor.execute("""
                    INSERT INTO academic_members (full_name, member_type, is_active)
                    VALUES (?, 'researcher', 1)
                """, (name,))
                
                new_member_id = cursor.lastrowid
                
                # Insert into researcher_details
                cursor.execute("""
                    INSERT INTO researcher_details (member_id)
                    VALUES (?)
                """, (new_member_id,))
                
                migrated_count += 1
                
        conn.commit()
        print(f"Migration complete. Migrated {migrated_count} new researchers.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_researchers()
