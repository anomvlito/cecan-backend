#!/usr/bin/env python3
"""
Script rápido para comparar ambas tablas de publicaciones
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("🔍 COMPARACIÓN DE TABLAS DE PUBLICACIONES")
print("=" * 80)

for table_name in ['Publicaciones', 'publicaciones']:
    print(f"\n📊 Tabla: {table_name}")
    print("-" * 80)
    
    try:
        # Count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"   Total registros: {count}")
        
        if count > 0:
            # Schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"   Columnas: {len(columns)}")
            print(f"   Nombres: {', '.join(columns[:5])}...")
            
            # Sample
            cursor.execute(f"SELECT id, titulo FROM {table_name} LIMIT 3")
            print(f"\n   Muestra de títulos:")
            for id_val, titulo in cursor.fetchall():
                print(f"      [{id_val}] {titulo[:70]}...")
        else:
            print("   ⚠️  Tabla vacía")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")

conn.close()

print("\n" + "=" * 80)
