#!/usr/bin/env python3
"""
Matching MEJORADO: Usa variaciones de nombres para encontrar más conexiones
"""
import sqlite3
import sys
import os
from difflib import SequenceMatcher
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def normalize(text):
    if not text: return ""
    return text.lower().strip().replace('.', '').replace(',', '')

def match_improved():
    print("=" * 80)
    print("🚀 MATCHING MEJORADO (Con Variaciones)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Obtener investigadores con sus variaciones
    cursor.execute("""
        SELECT am.id, am.full_name, rd.name_variations 
        FROM academic_members am
        LEFT JOIN researcher_details rd ON am.id = rd.member_id
    """)
    researchers = cursor.fetchall()
    
    # 2. Obtener publicaciones
    cursor.execute("SELECT id, titulo, autores FROM publicaciones WHERE autores IS NOT NULL AND autores != ''")
    publications = cursor.fetchall()
    
    print(f"👨‍🔬 Investigadores: {len(researchers)}")
    print(f"📚 Publicaciones:  {len(publications)}")
    
    # Limpiar matches anteriores automáticos
    cursor.execute("DELETE FROM investigador_publicacion WHERE match_method = 'fuzzy_auto'")
    print("🗑️  Limpiando matches automáticos anteriores...")
    
    matches_found = 0
    
    print("\n🔄 Buscando conexiones...")
    for pub_id, pub_title, pub_authors in publications:
        pub_authors_norm = normalize(pub_authors)
        
        for res_id, res_name, variations in researchers:
            # Lista de nombres a probar para este investigador
            names_to_test = [res_name]
            if variations:
                names_to_test.extend(variations.split('|'))
            
            is_match = False
            match_score = 0
            matched_name = ""
            
            for name in names_to_test:
                name_norm = normalize(name)
                if len(name_norm) < 4: continue # Saltar iniciales muy cortas
                
                # Check 1: Nombre exacto en string de autores
                if name_norm in pub_authors_norm:
                    is_match = True
                    match_score = 100
                    matched_name = name
                    break
                
                # Check 2: Similitud Fuzzy (para errores tipográficos)
                # Solo si el nombre es suficientemente largo
                if len(name) > 5:
                    # Buscar en partes del string de autores
                    # Esto es costoso, así que lo hacemos simple
                    if SequenceMatcher(None, name_norm, pub_authors_norm).find_longest_match(0, len(name_norm), 0, len(pub_authors_norm)).size > len(name_norm) * 0.9:
                         is_match = True
                         match_score = 90
                         matched_name = name
                         break
            
            if is_match:
                # Verificar duplicados
                cursor.execute("SELECT id FROM investigador_publicacion WHERE member_id = ? AND publicacion_id = ?", (res_id, pub_id))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO investigador_publicacion (member_id, publicacion_id, match_score, match_method)
                        VALUES (?, ?, ?, ?)
                    """, (res_id, pub_id, match_score, 'fuzzy_auto_v2'))
                    matches_found += 1
                    
                    if matches_found <= 5:
                        print(f"✅ Match: {res_name} (por '{matched_name}') ↔ {pub_title[:30]}...")

    conn.commit()
    conn.close()
    
    print(f"\n✨ Total de nuevos matches: {matches_found}")
    print("💡 Ejecuta 'python3 scripts/matching_reports.py' para ver el resultado final")

if __name__ == "__main__":
    match_improved()
