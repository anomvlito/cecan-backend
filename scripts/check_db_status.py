"""
Script para verificar el estado completo de la base de datos
"""
import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

def main():
    print(f"📍 Ruta de la base de datos: {DB_PATH}")
    print(f"✓ Archivo existe: {os.path.exists(DB_PATH)}")
    print(f"📦 Tamaño: {os.path.getsize(DB_PATH) / (1024*1024):.2f} MB\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("=" * 80)
    print(f"📊 RESUMEN DE TABLAS ({len(tables)} tablas encontradas)")
    print("=" * 80)
    
    important_tables = {
        'publicaciones': 'Artículos científicos',
        'academic_members': 'Miembros académicos (investigadores, estudiantes)',
        'researcher_details': 'Detalles de investigadores',
        'student_details': 'Detalles de estudiantes',
        'Investigadores': 'Investigadores (tabla legacy)',
        'Proyectos': 'Proyectos de investigación',
        'users': 'Usuarios del sistema',
        'publication_chunks': 'Chunks para RAG/IA'
    }
    
    table_data = []
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        table_data.append((table_name, count))
    
    # Mostrar tablas importantes primero
    print("\n🔑 TABLAS PRINCIPALES:")
    print("-" * 80)
    for table_name, description in important_tables.items():
        count = next((c for t, c in table_data if t == table_name), 0)
        status = "✅" if count > 0 else "⚠️ "
        print(f"{status} {table_name:30} → {count:>6} registros  ({description})")
    
    # Mostrar otras tablas
    other_tables = [(t, c) for t, c in table_data if t not in important_tables]
    if other_tables:
        print("\n📋 OTRAS TABLAS:")
        print("-" * 80)
        for table_name, count in other_tables:
            status = "✅" if count > 0 else "⚠️ "
            print(f"{status} {table_name:30} → {count:>6} registros")
    
    # Diagnóstico
    print("\n" + "=" * 80)
    print("🔍 DIAGNÓSTICO")
    print("=" * 80)
    
    pub_count = next((c for t, c in table_data if t == 'publicaciones'), 0)
    members_count = next((c for t, c in table_data if t == 'academic_members'), 0)
    
    if pub_count == 0:
        print("\n⚠️  NO HAY PUBLICACIONES")
        print("   Para sincronizar publicaciones desde la web:")
        print("   1. Inicia el servidor: python main.py")
        print("   2. Ejecuta: curl -X POST http://localhost:8000/api/sync-publications")
        print("   O usa el endpoint desde la documentación: http://localhost:8000/docs")
    else:
        print(f"\n✅ Hay {pub_count} publicaciones en la base de datos")
    
    if members_count == 0:
        print("\n⚠️  NO HAY MIEMBROS ACADÉMICOS")
        print("   Para sincronizar el staff desde la web:")
        print("   1. Inicia el servidor: python main.py")
        print("   2. Ejecuta: curl -X POST http://localhost:8000/api/sync-staff")
    else:
        print(f"\n✅ Hay {members_count} miembros académicos en la base de datos")
    
    conn.close()

if __name__ == "__main__":
    main()
