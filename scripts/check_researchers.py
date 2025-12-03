#!/usr/bin/env python3
"""
Verificar existencia de investigadores específicos para corrección manual
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def check_researchers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    names_to_check = [
        '%Roa%', 
        '%Colombo%', 
        '%Contreras%', 
        '%Montecinos%'
    ]
    
    print("🔍 Buscando investigadores existentes...")
    for name_pattern in names_to_check:
        cursor.execute("SELECT id, full_name FROM academic_members WHERE full_name LIKE ?", (name_pattern,))
        results = cursor.fetchall()
        for res in results:
            print(f"   Encontrado: ID {res[0]} - {res[1]}")

    conn.close()

if __name__ == "__main__":
    check_researchers()
