import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

def inspect_schema():
    print(f"Inspecting schema for database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    table_name = "proyecto_investigador"
    print(f"\n--- Table: {table_name} ---")
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        if not columns:
            print(f"Table {table_name} not found.")
        else:
            for col in columns:
                print(f"Column: {col[1]} (Type: {col[2]})")
    except Exception as e:
        print(f"Error inspecting table: {e}")
        
    conn.close()

if __name__ == "__main__":
    inspect_schema()
