import sys
import os
import sqlite3

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH

def inspect_table(table_name):
    print(f"\nInspecting table: {table_name}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f" - {col[1]} ({col[2]})")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_table("academic_members")
    inspect_table("proyecto_investigador")
    inspect_table("proyectos")
