"""
Migration Script: Add has_doi field to publications table
This script adds a pre-computed boolean field for performance optimization
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal, engine
from core.models import Publication
from sqlalchemy import text

def run_migration():
    print("🔄 Starting migration: Add has_doi field to publications")
    
    db = SessionLocal()
    
    try:
        # Step 1: Add column (if not exists)
        print("\n📝 Step 1: Adding has_doi column...")
        db.execute(text("""
            ALTER TABLE publications 
            ADD COLUMN IF NOT EXISTS has_doi BOOLEAN DEFAULT FALSE NOT NULL;
        """))
        db.commit()
        print("   ✅ Column added successfully")
        
        # Step 2: Create index for performance
        print("\n📝 Step 2: Creating index on has_doi...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_publications_has_doi 
            ON publications(has_doi);
        """))
        db.commit()
        print("   ✅ Index created successfully")
        
        # Step 3: Backfill existing data
        print("\n📝 Step 3: Backfilling has_doi for existing publications...")
        db.execute(text("""
            UPDATE publications
            SET has_doi = (
                canonical_doi IS NOT NULL 
                OR (url IS NOT NULL AND (url LIKE '%10.%' OR url LIKE '%doi.org%'))
            )
            WHERE has_doi = FALSE;
        """))
        db.commit()
        
        # Get stats
        total = db.execute(text("SELECT COUNT(*) FROM publications")).scalar()
        with_doi = db.execute(text("SELECT COUNT(*) FROM publications WHERE has_doi = TRUE")).scalar()
        without_doi = total - with_doi
        
        print(f"\n📊 Backfill Results:")
        print(f"   📚 Total publications: {total}")
        print(f"   ✅ With DOI: {with_doi}")
        print(f"   ⚠️  Without DOI: {without_doi}")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
