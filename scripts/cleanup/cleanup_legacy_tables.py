#!/usr/bin/env python3
"""
Script para limpiar tablas legacy (con mayúsculas) de la base de datos
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def main():
    print("=" * 80)
    print("🗑️  LIMPIEZA DE TABLAS LEGACY")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in cursor.fetchall()]
    
    # Tablas que podemos eliminar (legacy con mayúsculas)
    legacy_tables = {
        'Publicaciones': 'publicaciones',  # Reemplazada por minúscula
        'Investigadores': 'academic_members',  # Reemplazada por academic_members
        'Proyectos': 'proyectos',  # Existe versión minúscula
    }
    
    # Tablas que NO debemos tocar
    keep_tables = [
        'publicaciones',  # Tabla actual
        'academic_members',  # Tabla actual
        'researcher_details',  # Tabla actual
        'student_details',  # Tabla actual
        'users',  # Tabla actual
        'wps',  # Working packages
        'proyectos',  # Proyectos (minúscula)
        'nodos',  # Nodos
        'proyecto_investigador',  # Relaciones
        'proyecto_nodo',  # Relaciones
        'PublicationChunks',  # RAG/IA
        'publication_chunks',  # RAG/IA
        'investigador_publicacion',  # Relaciones
        'sqlite_sequence',  # Sistema SQLite
    ]
    
    print("\n📊 ANÁLISIS DE TABLAS")
    print("-" * 80)
    
    # Mostrar tablas legacy que podemos eliminar
    print("\n🔴 TABLAS LEGACY (candidatas para eliminar):")
    tables_to_drop = []
    for table in legacy_tables:
        if table in all_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            replacement = legacy_tables[table]
            print(f"   • {table:30} → {count:>6} registros (reemplazada por '{replacement}')")
            tables_to_drop.append(table)
    
    if not tables_to_drop:
        print("   ✅ No hay tablas legacy para eliminar")
        conn.close()
        return
    
    # Mostrar tablas que mantendremos
    print("\n✅ TABLAS QUE SE MANTENDRÁN:")
    for table in keep_tables:
        if table in all_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   • {table:30} → {count:>6} registros")
    
    # Confirmación
    print("\n" + "=" * 80)
    print("⚠️  CONFIRMACIÓN")
    print("=" * 80)
    print(f"\nSe eliminarán {len(tables_to_drop)} tablas legacy:")
    for table in tables_to_drop:
        print(f"   - {table}")
    
    response = input("\n¿Continuar con la eliminación? (escribe 'SI' para confirmar): ")
    
    if response != 'SI':
        print("\n❌ Operación cancelada")
        conn.close()
        return
    
    # Eliminar tablas
    print("\n🗑️  Eliminando tablas...")
    for table in tables_to_drop:
        try:
            print(f"   Eliminando {table}...", end=" ")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print("✅")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ LIMPIEZA COMPLETADA")
    print("=" * 80)
    print("\n💡 Verifica el resultado con:")
    print("   python3 scripts/check_db_status.py")

if __name__ == "__main__":
    main()
