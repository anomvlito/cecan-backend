#!/usr/bin/env python3
"""
Scraper FINAL con REGEX - Extrae datos del texto plano
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import sys
import os
import time
import re
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_metadata_with_regex(detail_url):
    """
    Extrae metadatos usando REGEX del texto plano
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Obtener texto completo y limpiar
        full_text = soup.get_text()
        clean_text = re.sub(r'\s+', ' ', full_text).strip()
        
        metadata = {
            'autores': '',
            'fecha': '',
            'resumen': ''
        }
        
        # 1. AUTORES - Entre "Autores" y "Fecha de publicación"
        autores_match = re.search(r'Autores\s+(.+?)\s+Fecha de publicación', clean_text)
        if autores_match:
            autores_raw = autores_match.group(1).strip()
            # Limpiar y formatear (los nombres están separados por espacios)
            # Asumimos que cada nombre completo tiene 2-3 palabras
            metadata['autores'] = autores_raw
        
        # 2. FECHA - Patrón "3 de octubre de 2025"
        fecha_match = re.search(r'Fecha de publicación\s+(.+?)\s+(?:Revista|Descargar)', clean_text)
        if fecha_match:
            metadata['fecha'] = fecha_match.group(1).strip()
        else:
            # Fallback: fecha corta del listado
            fecha_short = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', clean_text)
            if fecha_short:
                metadata['fecha'] = fecha_short.group(1)
        
        # 3. RESUMEN - Entre "Sobre esta publicación" y "Visualizar publicación"
        resumen_match = re.search(r'Sobre esta publicación\s*(.+?)\s+Visualizar publicación', clean_text, re.DOTALL)
        if resumen_match:
            metadata['resumen'] = resumen_match.group(1).strip()[:1000]  # Limitar a 1000 chars
        
        return metadata
        
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
        return None

def scrape_cecan_with_regex():
    """
    Scraping con regex - versión final
    """
    print("🌐 Scraping con REGEX...")
    print("-" * 80)
    
    url = "https://cecan.cl/publicaciones/?cat=cientificas"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # NIVEL 1: Listado
        print("📋 Nivel 1: Obteniendo listado...")
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        publications = []
        detail_buttons = soup.find_all('a', string=lambda t: t and "Ver detalles" in t)
        
        print(f"   ✅ Encontrados {len(detail_buttons)} publicaciones\n")
        
        # NIVEL 2: Detalles con regex
        print(f"📄 Nivel 2: Extrayendo metadatos con REGEX...")
        print("   (Esto tomará ~2 minutos)\n")
        
        for i, btn in enumerate(detail_buttons, 1):
            detail_url = btn.get('href')
            if not detail_url:
                continue
            
            if not detail_url.startswith('http'):
                detail_url = 'https://cecan.cl' + detail_url
            
            # Título del contenedor
            container = btn.find_parent('article') or btn.parent.parent
            title_tag = container.find('h3') or container.find('h4')
            title = title_tag.get_text(strip=True) if title_tag else "Sin título"
            
            # PDF URL
            download_btn = container.find('a', string=lambda t: t and "Descargar" in t)
            pdf_url = download_btn.get('href') if download_btn else ""
            
            print(f"   [{i}/{len(detail_buttons)}] {title[:50]}...", end=" ")
            
            # Extraer metadatos con regex
            metadata = extract_metadata_with_regex(detail_url)
            
            if metadata:
                publications.append({
                    'titulo': title,
                    'autores': metadata['autores'],
                    'fecha': metadata['fecha'],
                    'resumen': metadata['resumen'],
                    'url_origen': pdf_url,
                    'categoria': 'Científica'
                })
                print("✅")
            else:
                print("⚠️")
            
            time.sleep(0.5)  # Pausa para no saturar
        
        print(f"\n✅ Scraping completado: {len(publications)} publicaciones")
        return publications
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def enrich_with_regex():
    """
    Enriquece publicaciones con datos extraídos por regex
    """
    print("=" * 80)
    print("📚 ENRIQUECIMIENTO CON REGEX")
    print("=" * 80)
    print()
    
    # 1. Scrape
    web_pubs = scrape_cecan_with_regex()
    
    if not web_pubs:
        print("\n❌ No se pudieron obtener metadatos")
        return
    
    # 2. Conectar BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, titulo FROM publicaciones")
    db_pubs = cursor.fetchall()
    
    print(f"\n📊 Publicaciones en BD: {len(db_pubs)}")
    print(f"🌐 Metadatos scraped: {len(web_pubs)}")
    
    # 3. Matching y actualización
    print("\n🔄 Actualizando base de datos...")
    print("-" * 80)
    
    matched = 0
    updated = 0
    
    for db_id, db_title in db_pubs:
        best_match = None
        best_score = 0
        
        for web_pub in web_pubs:
            score = similarity(db_title, web_pub['titulo'])
            if score > best_score:
                best_score = score
                best_match = web_pub
        
        if best_match and best_score > 0.7:
            matched += 1
            
            cursor.execute("""
                UPDATE publicaciones 
                SET autores = ?,
                    fecha = ?,
                    url_origen = ?,
                    contenido_texto = CASE 
                        WHEN contenido_texto IS NULL OR contenido_texto = '' 
                        THEN ? 
                        ELSE contenido_texto 
                    END
                WHERE id = ?
            """, (
                best_match['autores'] or '',
                best_match['fecha'] or '',
                best_match['url_origen'] or '',
                best_match['resumen'] or '',
                db_id
            ))
            
            updated += 1
            
            if updated <= 5:
                print(f"✅ [{db_id}] {db_title[:50]}...")
                print(f"    Autores: {best_match['autores'][:60] if best_match['autores'] else 'N/A'}...")
                print(f"    Fecha: {best_match['fecha']}")
            elif updated % 20 == 0:
                print(f"   ... {updated} actualizadas ...")
    
    conn.commit()
    conn.close()
    
    # 4. Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"✅ Matches:      {matched}")
    print(f"✅ Actualizadas: {updated}")
    print(f"⚠️  Sin match:   {len(db_pubs) - matched}")
    
    print("\n💡 Verifica:")
    print("   python3 scripts/explore_publications.py")

if __name__ == "__main__":
    enrich_with_regex()
