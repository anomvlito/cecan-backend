#!/usr/bin/env python3
"""
Diagnóstico: Verifica si los datos de researcher_details existen en la BD
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def debug_details():
    print("=" * 80)
    print("🕵️  DIAGNÓSTICO DE DATOS DE INVESTIGADORES")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Consultar los primeros 5 investigadores y sus detalles
    cursor.execute("""
        SELECT 
            am.id, 
            am.full_name, 
            rd.first_name, 
            rd.last_name, 
            rd.orcid,
            rd.name_variations
        FROM academic_members am
        LEFT JOIN researcher_details rd ON am.id = rd.member_id
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    
    print(f"{'ID':<4} {'Nombre Completo':<25} {'First Name':<15} {'Last Name':<15} {'ORCID':<20}")
    print("-" * 85)
    
    for row in rows:
        print(f"{row['id']:<4} {row['full_name'][:24]:<25} {str(row['first_name'])[:14]:<15} {str(row['last_name'])[:14]:<15} {str(row['orcid']):<20}")

    conn.close()

if __name__ == "__main__":
    debug_details()
