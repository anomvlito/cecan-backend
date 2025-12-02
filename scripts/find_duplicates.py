#!/usr/bin/env python3
"""
Detecta y reporta duplicados en publicaciones
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def find_duplicates():
    print("=" * 80)
    print("🔍 BUSCANDO DUPLICADOS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Buscar publicaciones con títulos duplicados
    print("\n📚 PUBLICACIONES DUPLICADAS (mismo título):")
    print("-" * 80)
    cursor.execute("""
        SELECT titulo, COUNT(*) as count, GROUP_CONCAT(id) as ids
        FROM publicaciones
        GROUP BY titulo
        HAVING count > 1
        ORDER BY count DESC
    """)
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"\n   Encontrados {len(duplicates)} títulos duplicados:\n")
        for titulo, count, ids in duplicates[:20]:
            print(f"   [{count}x] {titulo[:60]}...")
            print(f"        IDs: {ids}")
    else:
        print("\n   ✅ No hay duplicados de títulos")
    
    # Buscar investigadores con nombres raros
    print("\n\n👥 INVESTIGADORES CON NOMBRES SOSPECHOSOS:")
    print("-" * 80)
    cursor.execute("""
        SELECT id, full_name
        FROM academic_members
        WHERE full_name LIKE '%,%'
        ORDER BY full_name
    """)
    
    weird_names = cursor.fetchall()
    
    if weird_names:
        print(f"\n   Encontrados {len(weird_names)} nombres con comas:\n")
        for id_val, name in weird_names:
            print(f"   [{id_val}] {name}")
    else:
        print("\n   ✅ No hay nombres con comas")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("💡 RECOMENDACIONES")
    print("=" * 80)
    print("""
    1. Eliminar publicaciones duplicadas manualmente
    2. Corregir nombres de investigadores con comas
    3. Re-ejecutar el matching después de limpiar
    """)

if __name__ == "__main__":
    find_duplicates()
