"""
Script para investigar la discrepancia entre PublicationChunks y Publicaciones
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def investigate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("🔍 INVESTIGANDO DISCREPANCIA DE DATOS")
    print("=" * 80)
    
    # Check PublicationChunks
    cursor.execute("SELECT COUNT(*) FROM PublicationChunks")
    chunks_count = cursor.fetchone()[0]
    print(f"\n📦 PublicationChunks: {chunks_count} registros")
    
    if chunks_count > 0:
        # Get sample
        cursor.execute("PRAGMA table_info(PublicationChunks)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Columnas: {', '.join(columns)}")
        
        cursor.execute("SELECT * FROM PublicationChunks LIMIT 1")
        sample = cursor.fetchone()
        print(f"\n   Muestra del primer registro:")
        for col, val in zip(columns, sample):
            if isinstance(val, str) and len(val) > 100:
                val = val[:100] + "..."
            print(f"      {col}: {val}")
    
    # Check both publication tables
    print("\n" + "=" * 80)
    print("📚 TABLAS DE PUBLICACIONES")
    print("=" * 80)
    
    for table_name in ['Publicaciones', 'publicaciones']:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"\n📄 {table_name}: {count} registros")
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Columnas: {', '.join(columns)}")
    
    # Check if there's a relationship
    print("\n" + "=" * 80)
    print("🔗 ANÁLISIS DE RELACIONES")
    print("=" * 80)
    
    # Try to find publication IDs in chunks
    if chunks_count > 0:
        cursor.execute("SELECT DISTINCT publication_id FROM PublicationChunks LIMIT 10")
        pub_ids = [row[0] for row in cursor.fetchall()]
        print(f"\n   IDs de publicaciones en chunks: {pub_ids}")
        
        # Check if these IDs exist in Publicaciones
        if pub_ids:
            placeholders = ','.join('?' * len(pub_ids))
            cursor.execute(f"SELECT id FROM Publicaciones WHERE id IN ({placeholders})", pub_ids)
            existing = [row[0] for row in cursor.fetchall()]
            print(f"   IDs que existen en Publicaciones: {existing}")
            print(f"   IDs faltantes: {set(pub_ids) - set(existing)}")
    
    # Check publication_chunks (lowercase)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='publication_chunks'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM publication_chunks")
        count = cursor.fetchone()[0]
        print(f"\n📄 publication_chunks (lowercase): {count} registros")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("💡 CONCLUSIÓN")
    print("=" * 80)
    print("""
    Parece que hay datos procesados para RAG (PublicationChunks)
    pero las tablas de publicaciones originales están vacías.
    
    Esto puede significar que:
    1. Los chunks se crearon pero luego se limpiaron las publicaciones
    2. Hay un problema de sincronización entre tablas
    3. Los chunks apuntan a publicaciones que ya no existen
    
    Recomendación: Ejecutar la sincronización completa para repoblar.
    """)

if __name__ == "__main__":
    investigate()
