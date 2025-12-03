"""
Script para inspeccionar la estructura real de la base de datos
"""
import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

def inspect_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print(f"INSPECCIONANDO BASE DE DATOS: {DB_PATH}")
    print("=" * 80)
    
    # Listar todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print(f"\n📊 TABLAS ENCONTRADAS ({len(tables)}):")
    print("-" * 80)
    for table in tables:
        table_name = table[0]
        
        # Contar registros
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        print(f"   • {table_name:<30} → {count:>8} registros")
    
    # Inspeccionar tablas que parecen de publicaciones
    print("\n" + "=" * 80)
    print("BUSCANDO TABLAS DE PUBLICACIONES")
    print("=" * 80)
    
    pub_tables = [t[0] for t in tables if 'public' in t[0].lower() or 'paper' in t[0].lower()]
    
    if not pub_tables:
        print("⚠️  No se encontraron tablas con 'public' o 'paper' en el nombre")
        print("\nMostrando TODAS las tablas con sus columnas:")
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print(f"\n📋 Tabla: {table_name}")
            for col in columns:
                col_id, col_name, col_type, not_null, default, pk = col
                print(f"      {col_name:<25} {col_type:<15} {'PK' if pk else ''}")
    else:
        for table_name in pub_tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print(f"\n📋 Tabla: {table_name}")
            print("   Columnas:")
            for col in columns:
                col_id, col_name, col_type, not_null, default, pk = col
                print(f"      {col_name:<25} {col_type:<15} {'PK' if pk else ''}")
            
            # Mostrar una muestra
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"\n   📊 Total de registros: {count}")
                
                # Obtener nombres de columnas
                col_names = [col[1] for col in columns]
                
                # Muestra de 2 registros
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
                rows = cursor.fetchall()
                
                print(f"\n   🔍 Muestra de datos:")
                for i, row in enumerate(rows, 1):
                    print(f"\n      Registro {i}:")
                    for col_name, value in zip(col_names, row):
                        if value and len(str(value)) > 100:
                            value = str(value)[:100] + "..."
                        print(f"         {col_name}: {value}")
    
    conn.close()

if __name__ == "__main__":
    inspect_database()
