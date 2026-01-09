#!/usr/bin/env python3
"""
Clear ALL ORCIDs from ALL researchers for clean slate
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def clear_all_orcids():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("🧹 Clearing ALL ORCIDs from ALL Researchers (Clean Slate)")
        print("=" * 80)
        
        sql = text("""
        UPDATE researcher_details
        SET 
            orcid = NULL,
            indice_h = NULL,
            citaciones_totales = NULL,
            works_count = NULL,
            i10_index = NULL,
            last_openalex_sync = NULL;
        """)
        
        result = db.execute(sql)
        db.commit()
        
        print(f"\n✅ Cleared ORCIDs from {result.rowcount} researchers")
        print("   Ready for clean re-enrichment")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_orcids()
