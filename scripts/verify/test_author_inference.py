#!/usr/bin/env python3
"""
Script de Testing: Sistema de Inferencia de Autores

Este script prueba automáticamente:
1. Encuentra publicaciones con DOI pero sin autores
2. Llama al endpoint /infer-authors en modo single
3. Verifica los resultados
4. Opcionalmente, prueba en modo batch

AUTENTICACIÓN: El script pedirá credenciales si no encuentra AUTH_TOKEN en ENV
"""

import sys
import os
import requests
import json
from datetime import datetime

# Add path for DB access
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_session
from core.models import Publication, ResearcherPublication

# Configuración
API_BASE_URL = "http://localhost:8000/api/publications"
AUTH_TOKEN = os.getenv('AUTH_TOKEN')  # Intentar desde ENV primero

def get_auth_token_interactive():
    """Obtiene token mediante login si no está en ENV."""
    print("\n🔐 No se encontró AUTH_TOKEN en variables de entorno")
    email = input("Email (presiona Enter para usar 'admin@cecan.cl'): ").strip() or "admin@cecan.cl"
    
    import getpass
    password = getpass.getpass("Password: ")
    
    login_url = "http://localhost:8000/api/auth/login"
    
    try:
        response = requests.post(login_url, json={"email": email, "password": password})
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ Login exitoso\n")
            return token
        else:
            print(f"❌ Login falló: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return None

def get_publications_without_authors(limit=10):
    """Encuentra publicaciones con DOI pero sin autores conectados."""
    session = get_session()
    
    try:
        # Query: Publicaciones con DOI que no tienen researcher_connections
        pubs = session.query(Publication).filter(
            Publication.canonical_doi.isnot(None)
        ).all()
        
        # Filtrar las que no tienen autores
        pubs_without_authors = []
        for pub in pubs:
            author_count = session.query(ResearcherPublication).filter(
                ResearcherPublication.publication_id == pub.id
            ).count()
            
            if author_count == 0:
                pubs_without_authors.append({
                    'id': pub.id,
                    'title': pub.title[:80] if pub.title else 'Sin título',
                    'doi': pub.canonical_doi,
                    'year': pub.year
                })
                
                if len(pubs_without_authors) >= limit:
                    break
        
        return pubs_without_authors
    
    finally:
        session.close()

def call_infer_authors_single(pub_id, auto_link=False, threshold=0.7):
    """Llama al endpoint /infer-authors en modo single."""
    url = f"{API_BASE_URL}/infer-authors"
    
    payload = {
        "mode": "single",
        "publication_id": pub_id,
        "auto_link": auto_link,
        "threshold": threshold
    }
    
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    
    print(f"\n{'='*60}")
    print(f"🔍 Llamando a API: POST {url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar al backend. ¿Está corriendo en localhost:8000?")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def call_infer_authors_batch(pub_ids, auto_link=False, threshold=0.7):
    """Llama al endpoint /infer-authors en modo batch."""
    url = f"{API_BASE_URL}/infer-authors"
    
    payload = {
        "mode": "batch",
        "publication_ids": pub_ids,
        "auto_link": auto_link,
        "threshold": threshold
    }
    
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    
    print(f"\n{'='*60}")
    print(f"🔍 Llamando a API BATCH: POST {url}")
    print(f"📦 Processing {len(pub_ids)} publications")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def display_results(result_data):
    """Muestra los resultados de forma legible."""
    if not result_data:
        print("⚠️ No hay resultados para mostrar")
        return
    
    results = result_data.get('results', [])
    
    print(f"\n{'='*60}")
    print(f"📊 RESULTADOS DE INFERENCIA")
    print(f"{'='*60}")
    
    for i, result in enumerate(results, 1):
        pub_id = result.get('publication_id')
        doi = result.get('doi', 'N/A')
        sources = ', '.join(result.get('sources_consulted', []))
        candidates = result.get('candidates', [])
        stats = result.get('stats', {})
        
        print(f"\n{i}. Publicación ID: {pub_id}")
        print(f"   DOI: {doi}")
        print(f"   Fuentes consultadas: {sources}")
        print(f"   Autores externos encontrados: {stats.get('total_external_authors', 0)}")
        print(f"   Matches encontrados: {stats.get('total_matches_found', 0)}")
        print(f"   Auto-linked: {stats.get('auto_linked', 0)}")
        print(f"   Skipped: {stats.get('skipped', 0)}")
        
        if candidates:
            print(f"\n   🔗 Candidatos:")
            for j, candidate in enumerate(candidates, 1):
                ext_author = candidate.get('external_author', 'N/A')
                matched = candidate.get('matched_member')
                score = candidate.get('score', 0)
                source = candidate.get('source', 'unknown')
                auto_linked = candidate.get('auto_linked', False)
                skipped = candidate.get('skipped_reason')
                
                print(f"\n   {j}. {ext_author} ({source})")
                if matched:
                    print(f"      ✅ Match: {matched.get('name')} ({matched.get('category')})")
                    print(f"      Score: {score:.2f} ({int(score*100)}%)")
                    if auto_linked:
                        print(f"      🔗 Auto-linked: SÍ")
                    elif skipped:
                        print(f"      ⏭️ Skipped: {skipped}")
                else:
                    print(f"      ❌ No match encontrado")
        else:
            print(f"   ⚠️ No se encontraron candidatos")

def main():
    global AUTH_TOKEN
    
    print("="*60)
    print("🧪 TESTING: Sistema de Inferencia de Autores")
    print("="*60)
    
    # Verificar autenticación
    if not AUTH_TOKEN:
        AUTH_TOKEN = get_auth_token_interactive()
        if not AUTH_TOKEN:
            print("\n❌ No se pudo obtener token de autenticación. Abortando.")
            return
    
    # Paso 1: Encontrar publicaciones para probar
    print("\n1️⃣ Buscando publicaciones con DOI pero sin autores...")
    pubs = get_publications_without_authors(limit=5)
    
    if not pubs:
        print("⚠️ No se encontraron publicaciones sin autores con DOI")
        print("   Prueba cambiando el filtro o agregando publicaciones manualmente")
        return
    
    print(f"\n✅ Encontradas {len(pubs)} publicaciones:")
    for i, pub in enumerate(pubs, 1):
        print(f"   {i}. ID {pub['id']}: {pub['title']} ({pub['year']})")
        print(f"      DOI: {pub['doi']}")
    
    # Paso 2: Probar modo SINGLE (sin auto-link primero)
    print(f"\n2️⃣ Probando modo SINGLE (auto_link=False)")
    test_pub = pubs[0]
    
    result = call_infer_authors_single(
        pub_id=test_pub['id'],
        auto_link=False,
        threshold=0.7
    )
    
    display_results(result)
    
    # Paso 3: Preguntar si quiere hacer auto-link
    if result and result.get('results', [{}])[0].get('candidates'):
        print("\n" + "="*60)
        response = input("\n¿Quieres ejecutar de nuevo con AUTO-LINK habilitado? (s/n): ")
        
        if response.lower() == 's':
            print("\n3️⃣ Probando modo SINGLE con AUTO-LINK...")
            result_linked = call_infer_authors_single(
                pub_id=test_pub['id'],
                auto_link=True,
                threshold=0.7
            )
            display_results(result_linked)
    
    # Paso 4: Probar modo BATCH
    if len(pubs) > 1:
        print("\n" + "="*60)
        response = input("\n¿Quieres probar modo BATCH con todas las publicaciones encontradas? (s/n): ")
        
        if response.lower() == 's':
            pub_ids = [p['id'] for p in pubs]
            print(f"\n4️⃣ Probando modo BATCH con {len(pub_ids)} publicaciones...")
            
            result_batch = call_infer_authors_batch(
                pub_ids=pub_ids,
                auto_link=False,
                threshold=0.7
            )
            
            display_results(result_batch)
    
    print("\n" + "="*60)
    print("✅ Testing completado")
    print("="*60)

if __name__ == "__main__":
    main()
