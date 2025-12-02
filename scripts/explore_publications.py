"""
Script para explorar la estructura de las publicaciones
y entender qué datos tenemos disponibles
"""
import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

def explore_publications():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get sample publications
    print("=" * 80)
    print("EXPLORANDO PUBLICACIONES EN LA BASE DE DATOS")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM publicaciones")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total de publicaciones: {total}")
    
    if total == 0:
        print("\n⚠️  No hay publicaciones en la base de datos.")
        print("   Verifica que hayas ejecutado los scripts de migración correctamente.")
        conn.close()
        return
    
    # Get publications with URLs
    cursor.execute("SELECT COUNT(*) FROM Publicaciones WHERE url_origen IS NOT NULL AND url_origen != ''")
    with_urls = cursor.fetchone()[0]
    print(f"🔗 Publicaciones con URL: {with_urls} ({with_urls/total*100:.1f}%)")
    
    # Get publications with authors
    cursor.execute("SELECT COUNT(*) FROM Publicaciones WHERE autores IS NOT NULL AND autores != ''")
    with_authors = cursor.fetchone()[0]
    print(f"👥 Publicaciones con autores: {with_authors} ({with_authors/total*100:.1f}%)")
    
    # Sample publications
    print("\n" + "=" * 80)
    print("MUESTRA DE 3 PUBLICACIONES")
    print("=" * 80)
    
    cursor.execute("""
        SELECT titulo, autores, url_origen, categoria 
        FROM Publicaciones 
        WHERE autores IS NOT NULL 
        LIMIT 3
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        titulo, autores, url, categoria = row
        print(f"\n📄 PUBLICACIÓN {i}")
        print(f"   Título: {titulo[:100]}...")
        print(f"   Categoría: {categoria}")
        print(f"   URL: {url[:80] if url else 'N/A'}...")
        print(f"   Autores: {autores[:150] if autores else 'N/A'}...")
    
    # Check for DOIs in URLs
    print("\n" + "=" * 80)
    print("ANÁLISIS DE DOIs")
    print("=" * 80)
    
    cursor.execute("""
        SELECT COUNT(*) FROM Publicaciones 
        WHERE url_origen LIKE '%doi.org%' 
        OR url_origen LIKE '%dx.doi.org%'
    """)
    with_doi = cursor.fetchone()[0]
    print(f"🔬 Publicaciones con DOI en URL: {with_doi} ({with_doi/total*100:.1f}%)")
    
    # Sample DOI URLs
    cursor.execute("""
        SELECT titulo, url_origen 
        FROM Publicaciones 
        WHERE url_origen LIKE '%doi.org%' 
        LIMIT 3
    """)
    
    print("\nEjemplos de URLs con DOI:")
    for titulo, url in cursor.fetchall():
        print(f"   • {titulo[:60]}...")
        print(f"     {url}")
    
    # Check researchers
    print("\n" + "=" * 80)
    print("INVESTIGADORES EN LA BASE DE DATOS")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM academic_members WHERE member_type = 'researcher'")
    total_researchers = cursor.fetchone()[0]
    print(f"👨‍🔬 Total de investigadores: {total_researchers}")
    
    cursor.execute("""
        SELECT full_name, email 
        FROM academic_members 
        WHERE member_type = 'researcher' 
        LIMIT 5
    """)
    
    print("\nMuestra de investigadores:")
    for name, email in cursor.fetchall():
        print(f"   • {name} ({email if email else 'sin email'})")
    
    conn.close()

if __name__ == "__main__":
    explore_publications()