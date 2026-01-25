#!/usr/bin/env python3
"""
Script para hacer scraping de metadatos de CECAN y enriquecer publicaciones existentes
NO descarga PDFs - solo obtiene metadatos y actualiza la BD
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import sys
import os
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def similarity(a, b):
    """Calcula similitud entre dos strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def scrape_cecan_metadata():
    """
    Scrape solo los METADATOS de publicaciones de CECAN
    (título, autores, fecha, URL, DOI)
    """
    print("🌐 Scraping metadatos de CECAN...")
    url = "https://cecan.cl/publicaciones/?cat=cientificas"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        publications = []
        
        # Estrategia: buscar botones "Descargar" y extraer info del contenedor
        download_buttons = soup.find_all('a', string=lambda t: t and "Descargar" in t)
        
        print(f"   Encontrados {len(download_buttons)} botones de descarga")
        
        for btn in download_buttons:
            try:
                # Encontrar contenedor padre
                container = btn.find_parent('article') or btn.parent.parent
                
                # Extraer título
                title_tag = container.find('h3') or container.find('h4') or container.find('h2')
                title = title_tag.get_text(strip=True) if title_tag else None
                
                # Extraer fecha
                date_tag = container.find('span', class_='date') or container.find('time')
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                # Extraer URL del PDF
                pdf_url = btn.get('href')
                
                # Intentar extraer autores (pueden estar en diferentes lugares)
                authors = ""
                author_tag = container.find('p', class_='authors') or container.find('span', class_='author')
                if author_tag:
                    authors = author_tag.get_text(strip=True)
                
                # Extraer DOI de la URL si existe
                doi = ""
                if pdf_url and 'doi.org' in pdf_url:
                    doi = pdf_url.split('doi.org/')[-1] if 'doi.org/' in pdf_url else ""
                
                if title and pdf_url:
                    publications.append({
                        "titulo": title,
                        "autores": authors,
                        "fecha": date,
                        "url_origen": pdf_url,
                        "doi": doi,
                        "categoria": "Científica"
                    })
                    
            except Exception as e:
                print(f"   ⚠️  Error procesando item: {e}")
                continue
        
        # Estrategia genérica si la primera falla
        if not publications:
            print("   Intentando estrategia genérica...")
            potential_titles = soup.find_all(['h3', 'h4'])
            for t in potential_titles:
                next_elems = t.find_all_next('a', limit=5)
                pdf_url = None
                for a in next_elems:
                    if "Descargar" in a.get_text() or "download" in str(a.get('class', [])):
                        pdf_url = a.get('href')
                        break
                
                if pdf_url:
                    title = t.get_text(strip=True)
                    prev = t.find_previous(text=True)
                    date = prev.strip() if prev and len(prev.strip()) < 20 else ""
                    
                    publications.append({
                        "titulo": title,
                        "autores": "",
                        "fecha": date,
                        "url_origen": pdf_url,
                        "doi": "",
                        "categoria": "Científica"
                    })
        
        print(f"✅ Scraped {len(publications)} publicaciones con metadatos")
        return publications
        
    except Exception as e:
        print(f"❌ Error en scraping: {e}")
        return []

def enrich_publications():
    """
    Enriquece las publicaciones existentes con metadatos del scraping
    """
    print("\n" + "=" * 80)
    print("📚 ENRIQUECIMIENTO DE PUBLICACIONES")
    print("=" * 80)
    
    # 1. Scrape metadatos
    web_pubs = scrape_cecan_metadata()
    
    if not web_pubs:
        print("\n❌ No se pudieron obtener metadatos del web")
        return
    
    # 2. Conectar a BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 3. Obtener publicaciones actuales
    cursor.execute("SELECT id, titulo FROM publicaciones")
    db_pubs = cursor.fetchall()
    
    print(f"\n📊 Publicaciones en BD: {len(db_pubs)}")
    print(f"🌐 Metadatos scraped: {len(web_pubs)}")
    
    # 4. Hacer matching por similitud de título
    print("\n🔄 Haciendo matching por título...")
    print("-" * 80)
    
    matched = 0
    updated = 0
    
    for db_id, db_title in db_pubs:
        best_match = None
        best_score = 0
        
        # Buscar mejor match
        for web_pub in web_pubs:
            score = similarity(db_title, web_pub['titulo'])
            if score > best_score:
                best_score = score
                best_match = web_pub
        
        # Si el match es bueno (>70%), actualizar
        if best_match and best_score > 0.7:
            matched += 1
            
            # Actualizar solo si hay datos nuevos
            updates = []
            params = []
            
            if best_match['autores'] and best_match['autores'].strip():
                updates.append("autores = ?")
                params.append(best_match['autores'])
            
            if best_match['fecha'] and best_match['fecha'].strip():
                updates.append("fecha = ?")
                params.append(best_match['fecha'])
            
            if best_match['url_origen'] and best_match['url_origen'].strip():
                updates.append("url_origen = ?")
                params.append(best_match['url_origen'])
            
            if updates:
                params.append(db_id)
                query = f"UPDATE publicaciones SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                updated += 1
                
                if updated <= 5:  # Mostrar primeros 5
                    print(f"✅ [{db_id}] {db_title[:50]}... (similitud: {best_score:.1%})")
                elif updated % 20 == 0:
                    print(f"   ... {updated} publicaciones actualizadas ...")
    
    conn.commit()
    conn.close()
    
    # 5. Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Matches encontrados:     {matched}")
    print(f"✅ Publicaciones actualizadas: {updated}")
    print(f"⚠️  Sin match:              {len(db_pubs) - matched}")
    
    print("\n💡 Próximos pasos:")
    print("   1. Verifica: python3 scripts/explore_publications.py")
    print("   2. Revisa los datos actualizados")

if __name__ == "__main__":
    enrich_publications()
