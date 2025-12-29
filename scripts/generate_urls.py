   python3 scripts/explore_publications.py
fabian@LAPTOP-L1FFBCH6:/mnt/d/0 one drive fgortega microsoft/OneDrive - Universidad Católica de Chile/0 antigravity/cecan-agent/backend$ python3 scripts/explore_publications.py
================================================================================
EXPLORANDO PUBLICACIONES EN LA BASE DE DATOS
================================================================================

📊 Total de publicaciones: 151
🔗 Publicaciones con URL: 151 (100.0%)
👥 Publicaciones con autores: 148 (98.0%)

================================================================================
MUESTRA DE 3 PUBLICACIONES
================================================================================

📄 PUBLICACIÓN 1
   Título: Genetic Ancestry, Intrinsic Tumor Subtypes, and Breast Cancer Survival in Latin American Women...
   Categoría: Científica
   URL: https://cecan.cl/publicaciones/cientificas/genetic-ancestry-intrinsic-tumor-subt...    
   Autores: Katherine Marcelain Bettina Müller...

📄 PUBLICACIÓN 2
   Título: Integrated clinico-molecular analysis of gastric cancer in European and Latin American populations: ...
   Categoría: Científica
   URL: https://cecan.cl/publicaciones/cientificas/integrated-clinico-molecular-analysis...    
   Autores: Erick Riquelme Juan Carlos Roa Gareth Owen...

📄 PUBLICACIÓN 3
   Título: SKI regulates rRNA transcription and pericentromeric heterochromatin to ensure centromere integrity ...
   Categoría: Científica
   URL: https://cecan.cl/publicaciones/cientificas/ski-regulates-rrna-transcription-and-...    
   Autores: Ricardo Armisén Katherine Marcelain...

================================================================================
ANÁLISIS DE DOIs
================================================================================
🔬 Publicaciones con DOI en URL: 0 (0.0%)

Ejemplos de URLs con DOI:

================================================================================
INVESTIGADORES EN LA BASE DE DATOS
================================================================================
👨‍🔬 Total de investigadores: 127

Muestra de investigadores:
   • Alejandra Fuentes (sin email)
   • Alexandra Obach (sin email)
   • Alicia Colombo, Juan Carlos Roa (sin email)
   • Alondra Castillo (sin email)
   • Andrea Canals (sin email)
fabian@LAPTOP-L1FFBCH6:/mnt/d/0 one drive fgortega microsoft/OneDrive - Universidad Católica de Chile/0 antigravity/cecan-agent/backend$#!/usr/bin/env python3
"""
Script para agregar URLs de detalles a las publicaciones
Genera URL desde el título: minúsculas + guiones en vez de espacios
"""
import sqlite3
import sys
import os
import re
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def slugify(text):
    """
    Convierte texto a formato slug (URL-friendly)
    Ejemplo: "Genetic Ancestry, Intrinsic Tumor" -> "genetic-ancestry-intrinsic-tumor"
    """
    # Normalizar unicode
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Convertir a minúsculas
    text = text.lower()
    
    # Reemplazar espacios y caracteres especiales por guiones
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    # Eliminar guiones al inicio y final
    text = text.strip('-')
    
    return text

def generate_detail_urls():
    """
    Genera URLs de detalles para todas las publicaciones
    """
    print("=" * 80)
    print("🔗 GENERANDO URLs DE DETALLES")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener publicaciones
    cursor.execute("SELECT id, titulo FROM publicaciones")
    publications = cursor.fetchall()
    
    print(f"\n📊 Total de publicaciones: {len(publications)}")
    print("\n🔄 Generando URLs...")
    print("-" * 80)
    
    updated = 0
    
    for pub_id, titulo in publications:
        # Generar slug del título
        slug = slugify(titulo)
        
        # Generar URL completa
        detail_url = f"https://cecan.cl/publicaciones/cientificas/{slug}/"
        
        # Actualizar en BD
        cursor.execute("""
            UPDATE publicaciones 
            SET url_origen = ?
            WHERE id = ?
        """, (detail_url, pub_id))
        
        updated += 1
        
        if updated <= 5:
            print(f"✅ [{pub_id}] {titulo[:50]}...")
            print(f"    URL: {detail_url[:80]}...")
        elif updated % 20 == 0:
            print(f"   ... {updated} URLs generadas ...")
    
    conn.commit()
    conn.close()
    
    print(f"\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ URLs generadas: {updated}")
    
    print("\n💡 Verifica:")
    print("   python3 scripts/explore_publications.py")

if __name__ == "__main__":
    generate_detail_urls()
