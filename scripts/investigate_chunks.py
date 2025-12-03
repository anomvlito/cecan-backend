#!/usr/bin/env python3
"""
Script para investigar los PublicationChunks y ver si podemos recuperar metadatos
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
    print("🔍 INVESTIGANDO PublicationChunks")
    print("=" * 80)
    
    # Check PublicationChunks
    cursor.execute("SELECT COUNT(*) FROM PublicationChunks")
    total_chunks = cursor.fetchone()[0]
    print(f"\n📦 Total de chunks: {total_chunks}")
    
    # Get schema
    cursor.execute("PRAGMA table_info(PublicationChunks)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"📋 Columnas: {', '.join(columns)}")
    
    # Check publication IDs referenced
    cursor.execute("SELECT DISTINCT publicacion_id FROM PublicationChunks LIMIT 10")
    pub_ids = [row[0] for row in cursor.fetchall()]
    print(f"\n🔗 IDs de publicaciones referenciadas (muestra): {pub_ids}")
    
    # Check if those IDs exist in publicaciones
    if pub_ids:
        placeholders = ','.join('?' * len(pub_ids))
        cursor.execute(f"SELECT id, titulo, autores FROM publicaciones WHERE id IN ({placeholders})", pub_ids)
        existing = cursor.fetchall()
        
        print(f"\n📊 Publicaciones encontradas en BD: {len(existing)}")
        if existing:
            print("\nMuestra:")
            for id_val, titulo, autores in existing[:3]:
                print(f"   [{id_val}] {titulo[:60]}...")
                print(f"        Autores: {autores if autores else 'N/A'}")
    
    # Sample chunk content
    cursor.execute("SELECT content FROM PublicationChunks LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        content = sample[0]
        print(f"\n📄 Muestra de contenido de chunk:")
        print(f"   {content[:200]}...")
    
    # Check if there are orphan chunks (publicacion_id not in publicaciones)
    cursor.execute("""
        SELECT COUNT(DISTINCT pc.publicacion_id) 
        FROM PublicationChunks pc
        LEFT JOIN publicaciones p ON pc.publicacion_id = p.id
        WHERE p.id IS NULL
    """)
    orphan_count = cursor.fetchone()[0]
    print(f"\n⚠️  Chunks huérfanos (sin publicación asociada): {orphan_count}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("💡 DIAGNÓSTICO")
    print("=" * 80)
    print(f"""
    Tienes {total_chunks} chunks procesados para RAG/IA.
    
    Estos chunks probablemente vienen de una importación anterior
    donde SÍ había metadatos completos (autores, DOIs, etc.).
    
    Opciones:
    1. Hacer scraping web para obtener metadatos actualizados
    2. Extraer metadatos de los PDFs usando IA (Gemini)
    3. Usar los chunks existentes si tienen la info completa
    """)

if __name__ == "__main__":
    main()
