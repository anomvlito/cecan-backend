#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

def add_wp_to_students():
    db = SessionLocal()
    try:
        # Check if table exists and column exists
        res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='students' AND column_name='wp_id'")).scalar()
        if not res:
            print("Adding wp_id column to students table...")
            db.execute(text("ALTER TABLE students ADD COLUMN wp_id INTEGER REFERENCES work_packages(id)"))
            db.commit()
            print("Column added successfully.")
        else:
            print("wp_id column already exists.")
            
        # Optional: Sync wp_id from AcademicMember by RUT/Email if possible
        print("Syncing wp_id from academic_members...")
        db.execute(text("""
            UPDATE students s
            SET wp_id = m.wp_id
            FROM academic_members m
            WHERE (s.rut = m.rut AND s.rut IS NOT NULL)
               OR (s.email = m.email AND s.email IS NOT NULL AND s.email != '')
        """))
        db.commit()
        print("Sync completed.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_wp_to_students()
