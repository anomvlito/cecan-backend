"""
Quick fix: Update anid_report_status default values to match enum
"""
import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Since the column has default 'Error', but we're using SQLAlchemy enums,
# we need to make sure there are no issues
# Let's just set all NULL or empty to 'Error' properly

cursor.execute("SELECT COUNT(*) FROM Publicaciones WHERE anid_report_status IS NULL OR anid_report_status = ''")
count = cursor.fetchone()[0]

if count > 0:
    print(f"Updating {count} publications with NULL/empty status to 'Error'")
    cursor.execute("UPDATE Publicaciones SET anid_report_status = 'Error' WHERE anid_report_status IS NULL OR anid_report_status = ''")
    conn.commit()
    print("[OK] Updated")
else:
    print("All publications already have status set")

conn.close()
print("Done!")
