#!/usr/bin/env python3
"""
Migración Simple: Agregar columnas OpenAlex
Ejecutar desde el directorio backend: python3 migrations/add_openalex_simple.py
"""

import sqlite3
from pathlib import Path

# Buscar cecan.db en el directorio actual (backend)
DB_PATH = Path("cecan.db")

if not DB_PATH.exists():
    print(f"❌ Error: No se encuentra cecan.db en el directorio actual")
    print(f"   Directorio actual: {Path.cwd()}")
    print(f"\n💡 Asegúrate de ejecutar desde el directorio backend:")
    print(f"   cd backend")
    print(f"   python3 migrations/add_openalex_simple.py")
    exit(1)

print(f"📊 Conectando a: {DB_PATH.absolute()}")
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

try:
    # Verificar columnas existentes
    cursor.execute("PRAGMA table_info(researcher_details)")
    columns = [col[1] for col in cursor.fetchall()]
    
    changes = 0
    
    # Agregar works_count
    if 'works_count' not in columns:
        print("➕ Agregando columna 'works_count'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN works_count INTEGER")
        changes += 1
    else:
        print("✓ Columna 'works_count' ya existe")
    
    # Agregar i10_index
    if 'i10_index' not in columns:
        print("➕ Agregando columna 'i10_index'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN i10_index INTEGER")
        changes += 1
    else:
        print("✓ Columna 'i10_index' ya existe")
    
    if changes > 0:
        conn.commit()
        print(f"\n✅ Migración completada: {changes} columna(s) agregada(s)")
    else:
        print("\n✅ No se requieren cambios")
    
    # Verificación
    cursor.execute("SELECT COUNT(*) FROM researcher_details")
    total = cursor.fetchone()[0]
    print(f"\n📈 Total investigadores: {total}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()

print("\n🎉 ¡Listo! Ahora puedes reiniciar el backend.")
