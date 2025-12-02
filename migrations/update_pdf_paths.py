"""
Script para actualizar las rutas de PDFs en la base de datos
después de mover los archivos de backend/data/pdfs a docs/pdfs
"""

import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

def update_pdf_paths():
    """Actualiza las rutas de PDFs en la base de datos"""
    print("[*] Actualizando rutas de PDFs en la base de datos...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar cuántos registros tienen rutas antiguas
    cursor.execute("""
        SELECT COUNT(*) FROM Publicaciones 
        WHERE path_pdf_local LIKE '%backend%data%' 
           OR path_pdf_local LIKE '%backend/data%'
    """)
    count_old = cursor.fetchone()[0]
    
    if count_old == 0:
        print("[OK] No hay rutas antiguas para actualizar")
        conn.close()
        return
    
    print(f"[INFO] Encontrado {count_old} registros con rutas antiguas")
    
    # Actualizar rutas con backslash (Windows)
    cursor.execute("""
        UPDATE Publicaciones 
        SET path_pdf_local = REPLACE(path_pdf_local, 'backend\\data\\pdfs', 'docs\\pdfs')
        WHERE path_pdf_local LIKE '%backend\\data\\pdfs%'
    """)
    affected_backslash = cursor.rowcount
    
    # Actualizar rutas con forward slash (Unix/guardadas manualmente)
    cursor.execute("""
        UPDATE Publicaciones 
        SET path_pdf_local = REPLACE(path_pdf_local, 'backend/data/pdfs', 'docs/pdfs')
        WHERE path_pdf_local LIKE '%backend/data/pdfs%'
    """)
    affected_slash = cursor.rowcount
    
    # También actualizar rutas absolutas si existen
    cursor.execute("""
        UPDATE Publicaciones 
        SET path_pdf_local = REPLACE(
            REPLACE(path_pdf_local, 'backend\\data', 'docs'),
            'backend/data', 'docs'
        )
        WHERE path_pdf_local LIKE '%backend%data%'
    """)
    
    conn.commit()
    total_affected = affected_backslash + affected_slash
    
    print(f"[OK] Actualizado {total_affected} registros:")
    print(f"   - Con backslash (\\): {affected_backslash}")
    print(f"   - Con slash (/): {affected_slash}")
    
    # Verificar algunas rutas actualizadas
    cursor.execute("SELECT path_pdf_local FROM Publicaciones WHERE path_pdf_local IS NOT NULL LIMIT 5")
    print("\n[INFO] Ejemplos de rutas actualizadas:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}")
    
    conn.close()
    print("\n[OK] Actualizacion completada exitosamente")

if __name__ == "__main__":
    update_pdf_paths()
