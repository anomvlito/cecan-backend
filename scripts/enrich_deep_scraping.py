#!/usr/bin/env python3
"""
Scraper profundo de CECAN - 2 niveles
Nivel 1: Listado de publicaciones
Nivel 2: Página de detalles de cada publicación (autores, fecha, etc.)
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import sys
import os
import time
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def similarity(a, b):
    """Calcula similitud entre dos strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def scrape_publication_details(detail_url):
    """
    Scrape la página de detalles de una publicación individual
    Extrae: autores, fecha, revista, DOI, etc.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        details = {
            'autores': '',
            'fecha': '',
            'revista': '',
            'doi': ''
        }
        
        # Buscar sección "Autores"
        autores_section = soup.find('h3', string=lambda t: t and 'Autores' in t)
        if autores_section:
            # Los autores suelen estar en una lista <ul> después del h3
            ul = autores_section.find_next('ul')
            if ul:
                autores = [li.get_text(strip=True) for li in ul.find_all('li')]
                details['autores'] = ', '.join(autores)
        
        # Buscar "Fecha de publicación"
        fecha_section = soup.find('h3', string=lambda t: t and 'Fecha' in t)
        if fecha_section:
            fecha_text = fecha_section.find_next('p')
            if fecha_text:
                details['fecha'] = fecha_text.get_text(strip=True)
        
        # Buscar "Revista o Institución"
        revista_section = soup.find('h3', string=lambda t: t and 'Revista' in t or t and 'Institución' in t)
        if revista_section:
            revista_text = revista_section.find_next('p')
            if revista_text:
                details['revista'] = revista_text.get_text(strip=True)
        
        # Buscar DOI en el texto o enlaces
        doi_link = soup.find('a', href=lambda h: h and 'doi.org' in h)
        if doi_link:
            doi_url = doi_link.get('href')
            if 'doi.org/' in doi_url:
                details['doi'] = doi_url.split('doi.org/')[-1]
        
        return details
        
    except Exception as e:
        print(f"      ⚠️  Error en detalles: {e}")
        return None

def scrape_cecan_deep():
    """
    Scraping profundo en 2 niveles:
    1. Listado de publicaciones
    2. Detalles de cada publicación
    """
    print("🌐 Scraping profundo de CECAN...")
    print("-" * 80)
    
    url = "https://cecan.cl/publicaciones/?cat=cientificas"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        # NIVEL 1: Listado
        print("📋 Nivel 1: Obteniendo listado...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        publications = []
        
        # Buscar botones "Ver detalles"
        detail_buttons = soup.find_all('a', string=lambda t: t and "Ver detalles" in t)
        
        print(f"   ✅ Encontrados {len(detail_buttons)} publicaciones")
        
        if not detail_buttons:
            print("   ⚠️  No se encontraron botones 'Ver detalles'")
            print("   Intentando estrategia alternativa...")
            # Estrategia alternativa si no encuentra los botones
            detail_buttons = soup.find_all('a', class_=lambda c: c and 'detail' in str(c).lower())
        
        # NIVEL 2: Detalles de cada publicación
        print(f"\n📄 Nivel 2: Obteniendo detalles de {len(detail_buttons)} publicaciones...")
        print("   (Esto puede tomar 1-2 minutos)")
        print()
        
        for i, btn in enumerate(detail_buttons, 1):
            detail_url = btn.get('href')
            
            if not detail_url:
                continue
            
            # Asegurar URL completa
            if not detail_url.startswith('http'):
                detail_url = 'https://cecan.cl' + detail_url
            
            # Obtener título del contenedor
            container = btn.find_parent('article') or btn.parent.parent
            title_tag = container.find('h3') or container.find('h4') or container.find('h2')
            title = title_tag.get_text(strip=True) if title_tag else "Sin título"
            
            # Buscar botón de descarga en el mismo contenedor
            download_btn = container.find('a', string=lambda t: t and "Descargar" in t)
            pdf_url = download_btn.get('href') if download_btn else ""
            
            # Mostrar progreso
            print(f"   [{i}/{len(detail_buttons)}] {title[:50]}...", end=" ")
            
            # Scrape detalles
            details = scrape_publication_details(detail_url)
            
            if details:
                publications.append({
                    'titulo': title,
                    'autores': details['autores'],
                    'fecha': details['fecha'],
                    'revista': details['revista'],
                    'doi': details['doi'],
                    'url_origen': pdf_url,
                    'url_detalles': detail_url,
                    'categoria': 'Científica'
                })
                print("✅")
            else:
                print("⚠️")
            
            # Pequeña pausa para no saturar el servidor
            time.sleep(0.5)
        
        print(f"\n✅ Scraping completado: {len(publications)} publicaciones con metadatos completos")
        return publications
        
    except Exception as e:
        print(f"❌ Error en scraping: {e}")
        import traceback
        traceback.print_exc()
        return []

def enrich_publications_deep():
    """
    Enriquece las publicaciones con scraping profundo
    """
    print("=" * 80)
    print("📚 ENRIQUECIMIENTO PROFUNDO DE PUBLICACIONES")
    print("=" * 80)
    print()
    
    # 1. Scrape profundo
    web_pubs = scrape_cecan_deep()
    
    if not web_pubs:
        print("\n❌ No se pudieron obtener metadatos")
        return
    
    # 2. Conectar a BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 3. Obtener publicaciones actuales
    cursor.execute("SELECT id, titulo FROM publicaciones")
    db_pubs = cursor.fetchall()
    
    print(f"\n📊 Publicaciones en BD: {len(db_pubs)}")
    print(f"🌐 Metadatos scraped: {len(web_pubs)}")
    
    # 4. Hacer matching
    print("\n🔄 Haciendo matching y actualizando...")
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
            
            # Actualizar con TODOS los campos
            cursor.execute("""
                UPDATE publicaciones 
                SET autores = ?,
                    fecha = ?,
                    url_origen = ?
                WHERE id = ?
            """, (
                best_match['autores'] or '',
                best_match['fecha'] or '',
                best_match['url_origen'] or '',
                db_id
            ))
            
            updated += 1
            
            if updated <= 5:
                print(f"✅ [{db_id}] {db_title[:50]}...")
                print(f"    Autores: {best_match['autores'][:60] if best_match['autores'] else 'N/A'}...")
                print(f"    Fecha: {best_match['fecha']}")
            elif updated % 20 == 0:
                print(f"   ... {updated} publicaciones actualizadas ...")
    
    conn.commit()
    conn.close()
    
    # 5. Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"✅ Matches encontrados:        {matched}")
    print(f"✅ Publicaciones actualizadas: {updated}")
    print(f"⚠️  Sin match:                 {len(db_pubs) - matched}")
    
    print("\n💡 Verifica los resultados:")
    print("   python3 scripts/explore_publications.py")

if __name__ == "__main__":
    enrich_publications_deep()
