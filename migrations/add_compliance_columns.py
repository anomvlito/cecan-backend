"""
Migration: Add compliance audit columns to Publicaciones table
Date: 2025-11-24
Description: Adds columns for El Robot compliance audit system
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

def add_compliance_columns():
    """Add compliance audit columns to the Publicaciones table."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Adding compliance audit columns to Publicaciones table...")
    
    # List of columns to add
    columns_to_add = [
        ("has_valid_affiliation", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("has_funding_ack", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("anid_report_status", "VARCHAR(50) DEFAULT 'Error' NOT NULL"),
        ("last_audit_date", "DATETIME"),
        ("audit_notes", "TEXT")
    ]
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(Publicaciones)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    added_count = 0
    
    for column_name, column_def in columns_to_add:
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE Publicaciones ADD COLUMN {column_name} {column_def}"
                print(f"  Adding column: {column_name}...")
                cursor.execute(sql)
                added_count += 1
                print(f"  [OK] Added: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"  [WARN] Could not add {column_name}: {e}")
        else:
            print(f"  [INFO] Column {column_name} already exists, skipping.")
    
    conn.commit()
    conn.close()
    
    print(f"\n[SUCCESS] Migration completed! Added {added_count} new columns.")
    print("\nNew columns:")
    print("  - has_valid_affiliation  -> TRUE if CECAN/UC affiliation found")
    print("  - has_funding_ack        -> TRUE if FONDAP/ANID acknowledgment found")
    print("  - anid_report_status     -> 'Ok', 'Warning', or 'Error'")
    print("  - last_audit_date        -> Timestamp of last audit")
    print("  - audit_notes            -> Automated audit observations")
    print("\nReady to run compliance audits!")

if __name__ == "__main__":
    add_compliance_columns()
