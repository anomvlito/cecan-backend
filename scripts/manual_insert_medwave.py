
import sys
import os
from datetime import datetime

# Add the parent directory (backend root) to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_session
from core.models import WosJournalMirror

def insert_medwave():
    """
    Manually inserts or updates the 'Medwave' journal entry in WosJournalMirror.
    Based on specific user request:
    12863	Medwave	Discontinued	Q3	42,3	0.8		0717-6384	0717-6384	['MEDICINE, GENERAL & INTERNAL']	{"MEDICINE, RESEARCH & EXPERIMENTAL"}	Medwave Estudios Limitada	CHILE	https://wos-journal.info/journalid/12863
    """
    db = get_session()
    try:
        wos_id = 12863
        print(f"Checking for WosJournalMirror with ID {wos_id}...")
        
        journal = db.query(WosJournalMirror).filter(WosJournalMirror.wos_id == wos_id).first()
        
        if journal:
            print(f"Journal found: {journal.journal_name}. Updating...")
        else:
            print("Journal not found. Creating new entry...")
            journal = WosJournalMirror(wos_id=wos_id)
            db.add(journal)

        # Map fields from request
        journal.journal_name = "Medwave"
        journal.status = "Discontinued"
        journal.best_quartile = "Q3"
        journal.best_ranking_percent = "42.3"
        journal.jif = "0.8"
        # five_year_jif was empty in request
        journal.issn = "0717-6384"
        journal.eissn = "0717-6384"
        
        # Categories: provided as string "['MEDICINE, GENERAL & INTERNAL']"
        # We will store as a proper list for the JSON column
        journal.categories = ['MEDICINE, GENERAL & INTERNAL']
        
        # Ranking Category: provided as '{"MEDICINE, RESEARCH & EXPERIMENTAL"}'
        # Cleaning up the curly braces to standard string
        journal.ranking_category = "MEDICINE, RESEARCH & EXPERIMENTAL"
        
        journal.publisher = "Medwave Estudios Limitada"
        journal.country = "CHILE"
        journal.source_url = "https://wos-journal.info/journalid/12863"
        journal.last_updated = datetime.utcnow()
        
        db.commit()
        print("✅ Successfully saved 'Medwave' (ID 12863) to database.")
        
    except Exception as e:
        print(f"❌ Error inserting journal: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    insert_medwave()
