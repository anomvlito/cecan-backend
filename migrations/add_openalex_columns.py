"""
Migración: Agregar columnas OpenAlex a researcher_details
Fecha: 2025-12-21
"""

import sqlite3
import sys
import os
from pathlib import Path

# Agregar el directorio backend al path para importar config
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Importar configuración del proyecto
try:
    from config import DB_PATH
except ImportError:
    # Fallback si no se puede importar config
    DB_PATH = backend_dir / "cecan.db"

def run_migration():
    """Ejecuta la migración para agregar columnas OpenAlex."""
    
    # Convertir a Path si es string
    db_path = Path(DB_PATH) if isinstance(DB_PATH, str) else DB_PATH
    
    if not db_path.exists():
        print(f"❌ Error: Base de datos no encontrada en {db_path.absolute()}")
        print(f"\n💡 Verifica que estés en el directorio correcto:")
        print(f"   - Directorio actual: {Path.cwd()}")
        print(f"   - Directorio backend: {backend_dir}")
        print(f"   - Ruta DB esperada: {db_path.absolute()}")
        sys.exit(1)
    
    print(f"📊 Conectando a base de datos: {db_path.absolute()}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Verificar si las columnas ya existen
        cursor.execute("PRAGMA table_info(researcher_details)")
        columns = [col[1] for col in cursor.fetchall()]
        
        changes_made = False
        
        # Agregar works_count si no existe
        if 'works_count' not in columns:
            print("➕ Agregando columna 'works_count'...")
            cursor.execute("ALTER TABLE researcher_details ADD COLUMN works_count INTEGER")
            changes_made = True
        else:
            print("✓ Columna 'works_count' ya existe")
        
        # Agregar i10_index si no existe
        if 'i10_index' not in columns:
            print("➕ Agregando columna 'i10_index'...")
            cursor.execute("ALTER TABLE researcher_details ADD COLUMN i10_index INTEGER")
            changes_made = True
        else:
            print("✓ Columna 'i10_index' ya existe")
        
        if changes_made:
            conn.commit()
            print("\n✅ Migración completada exitosamente")
        else:
            print("\n✅ No se requieren cambios, columnas ya existen")
        
        # Verificación
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(works_count) as with_works,
                COUNT(i10_index) as with_i10
            FROM researcher_details
        """)
        total, with_works, with_i10 = cursor.fetchone()
        print(f"\n📈 Estadísticas:")
        print(f"   Total investigadores: {total}")
        print(f"   Con works_count: {with_works}")
        print(f"   Con i10_index: {with_i10}")
        
    except sqlite3.Error as e:
        print(f"\n❌ Error durante la migración: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
