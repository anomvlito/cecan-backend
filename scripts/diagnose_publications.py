import sys
import os
from sqlalchemy import text

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import SessionLocal

def diagnose_publications():
    db = SessionLocal()
    try:
        # Consulta SQL para verificar el estado real
        query = text("""
        SELECT 
            p.id,
            SUBSTR(p.title, 1, 40) as title,
            p.enrichment_status,
            CASE WHEN p.local_path IS NOT NULL AND p.local_path != '' THEN '✅ YES' ELSE '❌ NO' END as has_path,
            CASE WHEN p.content IS NOT NULL AND LENGTH(p.content) > 0 THEN '✅ ' || LENGTH(p.content) || ' chars' ELSE '❌ EMPTY' END as content,
            CASE WHEN p.summary_es IS NOT NULL AND p.summary_es != '' THEN '✅ YES' ELSE '❌ NO' END as has_summary,
            (SELECT COUNT(*) FROM publication_chunks pc WHERE pc.publication_id = p.id) as chunks_count
        FROM publications p
        ORDER BY p.id DESC
        LIMIT 20;
        """)
        
        result = db.execute(query).fetchall()
        
        print("\n🔍 DIAGNÓSTICO DE PUBLICACIONES (Últimas 20)")
        print("="*120)
        
        # Headers
        headers = ["ID", "Título", "Status", "PDF Path", "Contenido", "Resumen", "Chunks RAG"]
        
        # Simple formatting 
        row_format = "{:<5} {:<45} {:<20} {:<10} {:<20} {:<10} {:<10}"
        print(row_format.format(*headers))
        print("-" * 120)
        
        for row in result:
            # Handle potential None values safely
            title = row[1] if row[1] else "No Title"
            status = row[2] if row[2] else "None"
            
            print(row_format.format(
                str(row[0]), 
                title, 
                status, 
                row[3], 
                row[4], 
                row[5], 
                str(row[6])
            ))
            
        print("\n" + "="*120)
        print("📋 ANÁLISIS")
        print("Si ves 'chunks_count' > 0 pero 'Status' es 'metadata_only', el frontend mostrará 'Sin PDF' (Ambar).")
        print("Esto indica una inconsistencia: Los datos están ahí, pero el estado no se actualizó.")
        print("="*120 + "\n")

    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_publications()
