#!/usr/bin/env python3
"""
Script para investigar la discrepancia entre tablas de publicaciones
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🔍 INVESTIGANDO TABLAS DE PUBLICACIONES")
    print("=" * 80)
    
    # Check both tables
    for table_name in ['Publicaciones', 'publicaciones']:
        print(f"\n📊 Tabla: {table_name}")
        print("-" * 80)
        
        try:
            # Count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Total registros: {count}")
            
            # Schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"   Columnas ({len(columns)}):")
            for col in columns[:10]:  # First 10 columns
                col_id, col_name, col_type, not_null, default, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                pk_mark = "PK" if pk else ""
                print(f"      - {col_name:30} {col_type:15} {nullable:10} {pk_mark}")
            
            if len(columns) > 10:
                print(f"      ... y {len(columns) - 10} columnas más")
            
            # Sample data
            if count > 0:
                cursor.execute(f"SELECT id, titulo, path_pdf_local FROM {table_name} LIMIT 3")
                print(f"\n   Muestra de datos:")
                for row in cursor.fetchall():
                    id_val, titulo, path = row
                    print(f"      ID {id_val}: {titulo[:60]}...")
                    print(f"              Path: {path if path else 'N/A'}")
        
        except sqlite3.OperationalError as e:
            print(f"   ❌ Error: {e}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("💡 CONCLUSIÓN")
    print("=" * 80)
    print("""
    SQLite es CASE-SENSITIVE para nombres de tablas en algunos contextos.
    Tienes DOS tablas diferentes:
    - 'Publicaciones' (con P mayúscula) - probablemente la tabla legacy
    - 'publicaciones' (con p minúscula) - la tabla actual de SQLAlchemy
    
    El script de importación está usando la tabla correcta (publicaciones).
    El script de diagnóstico está mirando la tabla incorrecta (Publicaciones).
    """)

if __name__ == "__main__":
    main()
