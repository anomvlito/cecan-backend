"""
Database Migration: Rename Spanish Columns to English
Run this script to align PostgreSQL schema with English naming conventions.

IMPORTANT: Backup your database before running this migration!
"""

import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory (.env in cecan-backend/)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Try both variable names for compatibility
DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("DATABASE_URL")

def run_migration():
    """Execute all column rename migrations."""
    
    # Parse DATABASE_URL
    # postgresql://cecan_user:cecan_password@localhost:5432/cecan_db
    if not DATABASE_URL:
        print("ERROR: SQLALCHEMY_DATABASE_URL not found in environment")
        return False
    
    print(f"Connecting to: {DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('//')[1], '***')}")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("\n=== Phase 1: Migrating 'publications' table ===")
        
        # Check if columns exist before renaming
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'publications' AND column_name IN ('titulo', 'autores', 'contenido_texto');
        """)
        existing_spanish_cols = [row[0] for row in cursor.fetchall()]
        
        if 'titulo' in existing_spanish_cols:
            print("  Renaming 'titulo' → 'title'...")
            cursor.execute("ALTER TABLE publications RENAME COLUMN titulo TO title;")
        else:
            print("  ⚠️  Column 'titulo' not found (already migrated or doesn't exist)")
        
        if 'autores' in existing_spanish_cols:
            print("  Renaming 'autores' → 'authors'...")
            cursor.execute("ALTER TABLE publications RENAME COLUMN autores TO authors;")
        else:
            print("  ⚠️  Column 'autores' not found (already migrated or doesn't exist)")
        
        if 'contenido_texto' in existing_spanish_cols:
            print("  Renaming 'contenido_texto' → 'content'...")
            cursor.execute("ALTER TABLE publications RENAME COLUMN contenido_texto TO content;")
        else:
            print("  ⚠️  Column 'contenido_texto' not found (already migrated or doesn't exist)")
        
        print("\n=== Phase 2: Migrating 'publication_chunks' table ===")
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'publication_chunks' AND column_name = 'publicacion_id';
        """)
        if cursor.fetchone():
            print("  Renaming 'publicacion_id' → 'publication_id'...")
            cursor.execute("ALTER TABLE publication_chunks RENAME COLUMN publicacion_id TO publication_id;")
        else:
            print("  ⚠️  Column 'publicacion_id' not found (already migrated or doesn't exist)")
        
        print("\n=== Phase 3: Migrating 'meeting_minutes' table (Optional) ===")
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'meeting_minutes' AND column_name IN ('fecha', 'titulo', 'resumen_ia');
        """)
        meeting_cols = [row[0] for row in cursor.fetchall()]
        
        if 'fecha' in meeting_cols:
            print("  Renaming 'fecha' → 'date'...")
            cursor.execute("ALTER TABLE meeting_minutes RENAME COLUMN fecha TO date;")
        else:
            print("  ⚠️  Column 'fecha' not found (already migrated or doesn't exist)")
        
        if 'titulo' in meeting_cols:
            print("  Renaming 'titulo' → 'title'...")
            cursor.execute("ALTER TABLE meeting_minutes RENAME COLUMN titulo TO title;")
        else:
            print("  ⚠️  Column 'titulo' not found (already migrated or doesn't exist)")
        
        if 'resumen_ia' in meeting_cols:
            print("  Renaming 'resumen_ia' → 'ai_summary'...")
            cursor.execute("ALTER TABLE meeting_minutes RENAME COLUMN resumen_ia TO ai_summary;")
        else:
            print("  ⚠️  Column 'resumen_ia' not found (already migrated or doesn't exist)")
        
        # Commit changes
        conn.commit()
        
        print("\n=== Verification ===")
        
        # Verify publications columns
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'publications' 
            ORDER BY ordinal_position;
        """)
        pub_cols = [row[0] for row in cursor.fetchall()]
        print(f"  Publications columns: {', '.join(pub_cols[:10])}...")
        
        # Check for English columns
        has_title = 'title' in pub_cols
        has_authors = 'authors' in pub_cols
        has_content = 'content' in pub_cols
        
        if has_title and has_authors and has_content:
            print("  ✅ Migration successful!")
        else:
            print("  ⚠️  Some columns may not have been renamed")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CECAN Backend - Spanish → English Column Migration")
    print("=" * 60)
    print("\nThis script will rename database columns to English naming.")
    print("It is safe to run multiple times (checks before renaming).\n")
    
    confirm = input("Proceed with migration? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Migration cancelled.")
        exit(0)
    
    success = run_migration()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("  1. Update backend models (PublicationChunk.publication_id)")
        print("  2. Update frontend TypeScript interfaces")
        print("  3. Update React components")
    else:
        print("\n❌ Migration failed. Check errors above.")
        print("Database has been rolled back to previous state.")
