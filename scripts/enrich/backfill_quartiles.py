import sys
import os

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from core.models import Publication
from sqlalchemy import or_

def backfill_quartiles():
    db = SessionLocal()
    try:
        # Find publications with analysis but no quartile
        pubs = db.query(Publication).filter(
            Publication.ai_journal_analysis.isnot(None),
            or_(Publication.quartile.is_(None), Publication.quartile == "")
        ).all()
        
        print(f"Found {len(pubs)} publications to check for backfill...")
        
        updated_count = 0
        for pub in pubs:
            analysis = pub.ai_journal_analysis
            if analysis and isinstance(analysis, dict):
                quartile = analysis.get("quartile_estimate")
                if quartile:
                    # Extract Q1/Q2 etc (first 2 chars)
                    q_val = quartile[:2].upper()
                    if q_val in ["Q1", "Q2", "Q3", "Q4"]:
                        pub.quartile = q_val
                        updated_count += 1
                        print(f"Updated Pub {pub.id}: {q_val}")
        
        if updated_count > 0:
            db.commit()
            print(f"Successfully backfilled {updated_count} publications.")
        else:
            print("No updates needed.")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting Quartile Backfill...")
    backfill_quartiles()
