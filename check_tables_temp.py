import sqlite3
import os
import sys

# Ensure we can import config
sys.path.append(os.getcwd())

try:
    from config import DB_PATH
except ImportError:
    # Fallback
    DB_PATH = "cecan.db"

def list_tables():
    print(f"Checking database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERROR: Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables found:")
    for t in tables:
        print(f" - {t[0]}")
    conn.close()

if __name__ == "__main__":
    list_tables()
