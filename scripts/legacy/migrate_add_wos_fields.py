"""
Add WOS Mirror fields to publication_impact table
"""
from sqlalchemy import text
from database.session import SessionLocal

def upgrade():
    db = SessionLocal()
    try:
        # Add new columns
        db.execute(text("""
            ALTER TABLE publication_impact 
            ADD COLUMN IF NOT EXISTS ranking_percentile FLOAT,
            ADD COLUMN IF NOT EXISTS source VARCHAR(50),
            ADD COLUMN IF NOT EXISTS match_confidence VARCHAR(50),
            ADD COLUMN IF NOT EXISTS wos_journal_id INTEGER;
        """))
        db.commit()
        print("✅ Migration successful: Added WOS Mirror fields to publication_impact")
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    upgrade()
