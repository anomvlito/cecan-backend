#!/usr/bin/env python3
"""
Fase 2: Validación y Matching de ORCIDs con API
Consulta la API pública de ORCID (con pausas de seguridad) para obtener nombres
y vincularlos con nuestros investigadores.
"""
import sqlite3
import sys
import os
import requests
import time
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_orcid_profile(orcid_id):
    """Consulta la API pública de ORCID"""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/person"
    headers = {
        "Accept": "application/json",
        "User-Agent": "CECAN-Agent/1.0 (mailto:admin@cecan.cl)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            name_data = data.get("name", {})
            if name_data:
                given = name_data.get("given-names", {}).get("value", "")
                family = name_data.get("family-name", {}).get("value", "")
                return f"{given} {family}".strip()
    except Exception as e:
        print(f"   ⚠️  Error API ({orcid_id}): {e}")
    return None

def match_orcids_to_researchers():
    print("=" * 80)
    print("🔗 VINCULANDO ORCIDs CON INVESTIGADORES (Vía API)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Obtener todos los ORCIDs extraídos únicos
    print("🔍 Recolectando ORCIDs únicos de la base de datos...")
    cursor.execute("SELECT extracted_orcids FROM publicaciones WHERE extracted_orcids IS NOT NULL")
    rows = cursor.fetchall()
    
    unique_orcids = set()
    for row in rows:
        if row[0]:
            for o in row[0].split(','):
                unique_orcids.add(o.strip())
    
    print(f"   🆔 Total ORCIDs únicos a verificar: {len(unique_orcids)}")
    
    # 2. Obtener investigadores para comparar
    cursor.execute("SELECT id, full_name FROM academic_members")
    researchers = cursor.fetchall()
    
    # 3. Procesar (con delay para respetar rate limits)
    print("\n🚀 Iniciando consultas a API ORCID (1 req/seg)...")
    print("-" * 80)
    
    matches_found = 0
    processed = 0
    
    for orcid_id in unique_orcids:
        processed += 1
        
        # Verificar si ya tenemos este ORCID asignado a alguien (optimización)
        cursor.execute("SELECT member_id FROM researcher_details WHERE orcid = ?", (orcid_id,))
        if cursor.fetchone():
            print(f"   [{processed}/{len(unique_orcids)}] {orcid_id} → Ya asignado (Saltando)")
            continue
            
        # Consultar API
        orcid_name = get_orcid_profile(orcid_id)
        
        if orcid_name:
            # Intentar match con nuestros investigadores
            best_score = 0
            best_researcher = None
            
            for res_id, res_name in researchers:
                score = similarity(res_name, orcid_name)
                if score > best_score:
                    best_score = score
                    best_researcher = (res_id, res_name)
            
            # Si hay match fuerte (>85%)
            if best_score > 0.85:
                res_id, res_name = best_researcher
                print(f"   ✅ MATCH! {orcid_id} ({orcid_name}) ↔ {res_name} ({best_score:.0%})")
                
                # Guardar en BD
                cursor.execute("UPDATE researcher_details SET orcid = ? WHERE member_id = ?", (orcid_id, res_id))
                conn.commit()
                matches_found += 1
            else:
                # print(f"   ❌ Sin match interno: {orcid_name}")
                pass
        else:
            print(f"   ⚠️  No se pudo obtener nombre para {orcid_id}")
            
        # PAUSA DE SEGURIDAD (Rate Limiting)
        time.sleep(1.0) 
        
        if processed % 10 == 0:
            print(f"   ... Procesados {processed}/{len(unique_orcids)} ...")

    conn.close()
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"   ✅ Nuevos investigadores con ORCID: {matches_found}")
    print(f"   🔄 Total procesados: {processed}")

if __name__ == "__main__":
    match_orcids_to_researchers()
