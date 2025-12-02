"""Check current status values in database"""
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

cursor.execute("SELECT DISTINCT anid_report_status FROM Publicaciones")
statuses = cursor.fetchall()

print("Current status values in database:")
for status in statuses:
    cursor.execute("SELECT COUNT(*) FROM Publicaciones WHERE anid_report_status = ?", (status[0],))
    count = cursor.fetchone()[0]
    print(f"  '{status[0]}' -> {count} publications")

conn.close()
