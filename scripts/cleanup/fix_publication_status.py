import sys
import os
from sqlalchemy import text
import asyncio

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import SessionLocal
from services.rag_service import get_semantic_engine

def fix_publications_status():
    db = SessionLocal()
    try:
        # 1. Identificar publicaciones inconsistentes (metadata_only pero con path y contenido)
        query_check = text("""
        SELECT id, title
        FROM publications 
        WHERE enrichment_status = 'metadata_only' 
          AND local_path IS NOT NULL 
          AND local_path != '' 
          AND content IS NOT NULL 
          AND LENGTH(content) > 100;
        """)
        
        candidates = db.execute(query_check).fetchall()
        print(f"📦 Se encontraron {len(candidates)} publicaciones 'metadata_only' que YA tienen PDF y Texto.")
        
        if not candidates:
            print("✅ Todo parece estar correcto con los estados (Status OK).")
            # Continuamos para revisar RAG...


        # 2. Corregir el Estado (SQL Update)
        update_query = text("""
        UPDATE publications 
        SET enrichment_status = 'pdf_attached' 
        WHERE enrichment_status = 'metadata_only' 
          AND local_path IS NOT NULL 
          AND local_path != '' 
          AND content IS NOT NULL 
          AND LENGTH(content) > 100;
        """)
        
        result = db.execute(update_query)
        db.commit()
        print(f"🛠️  Se corrigió el estado de {result.rowcount} publicaciones a 'pdf_attached'.")
        print("   (Ahora aparecerán en Azul en el frontend)")

        # 3. Disparar RAG Indexing para las que no tienen chunks (Opcional, pero recomendado)
        print("\n🔎 Verificando indexación RAG...")
        rag_query = text("""
        SELECT p.id, p.title 
        FROM publications p
        LEFT JOIN publication_chunks pc ON p.id = pc.publication_id
        WHERE p.local_path IS NOT NULL 
        GROUP BY p.id
        HAVING COUNT(pc.id) = 0;
        """)
        
        rag_missing = db.execute(rag_query).fetchall()
        print(f"⚠️  Se encontraron {len(rag_missing)} publicaciones con PDF pero SIN Chunks RAG (Indexación faltante).")
        
        if len(rag_missing) > 0:
            print("\n🔄 Iniciando re-indexación automática...")
            engine = get_semantic_engine()
            
            success_count = 0
            for row in rag_missing:
                pub_id = row[0]
                pub_title = row[1] or "Sin Título"
                print(f"   - Procesando ID {pub_id}: {pub_title[:40]}...")
                
                # Fetch fresh object or content? The engine fetches by ID.
                # process_single_publication handles fetching from DB.
                result = engine.process_single_publication(pub_id)
                
                if result.get("success"):
                    print(f"     ✅ Indexado ({result.get('chunks_created')} chunks)")
                    success_count += 1
                else:
                    print(f"     ❌ Error: {result.get('error')}")
            
            print(f"\n📊 Indexación completada: {success_count}/{len(rag_missing)} procesados correctamente.")


    except Exception as e:
        print(f"❌ Error during fix: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_publications_status()
