import sys
import os
import sqlite3

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH
from database.legacy_wrapper import CecanDB

def check_tables():
    print(f"Checking database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERROR: Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables found:")
    table_names = [t[0] for t in tables]
    for t in table_names:
        print(f" - {t}")
    conn.close()
    return table_names

def test_graph_data():
    print("\nTesting get_graph_data()...")
    db = CecanDB()
    try:
        data = db.get_graph_data()
        print("Success! Data keys:", data.keys())
        print(f"Nodes: {len(data['nodes'])}, Edges: {len(data['edges'])}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_tables()
    test_graph_data()
