#!/usr/bin/env python3
"""
Script para hacer matching entre investigadores y publicaciones
Vincula investigadores con publicaciones basándose en nombres de autores
"""
import sqlite3
import sys
import os
from difflib import SequenceMatcher
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def similarity(a, b):
    """Calcula similitud entre dos strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_name(name):
    """Normaliza un nombre para matching"""
    # Remover acentos y convertir a minúsculas
    name = name.lower().strip()
    # Remover puntos, comas, etc.
    name = re.sub(r'[.,;:]', '', name)
    return name

def extract_individual_names(authors_string):
    """
    Extrae nombres individuales de un string de autores
    Ejemplo: "Katherine Marcelain Bettina Müller" -> ["Katherine Marcelain", "Bettina Müller"]
    """
    if not authors_string:
        return []
    
    # Estrategia simple: asumimos que cada autor tiene 2 palabras (nombre + apellido)
    # o 3 palabras (nombre + apellido + apellido)
    words = authors_string.split()
    
    authors = []
    i = 0
    while i < len(words):
        # Intentar con 3 palabras primero
        if i + 2 < len(words):
            # Verificar si las 3 palabras forman un nombre válido
            # (primera letra mayúscula)
            if words[i][0].isupper() and words[i+1][0].isupper():
                authors.append(f"{words[i]} {words[i+1]} {words[i+2]}")
                i += 3
                continue
        
        # Intentar con 2 palabras
        if i + 1 < len(words):
            if words[i][0].isupper() and words[i+1][0].isupper():
                authors.append(f"{words[i]} {words[i+1]}")
                i += 2
                continue
        
        # Si no, saltar esta palabra
        i += 1
    
    return authors

def match_researchers_to_publications():
    """
    Hace matching entre investigadores y publicaciones
    """
    print("=" * 80)
    print("🔗 MATCHING INVESTIGADORES ↔ PUBLICACIONES")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Obtener investigadores
    cursor.execute("SELECT id, full_name FROM academic_members")
    researchers = cursor.fetchall()
    
    # 2. Obtener publicaciones con autores
    cursor.execute("""
        SELECT id, titulo, autores 
        FROM publicaciones 
        WHERE autores IS NOT NULL AND autores != ''
    """)
    publications = cursor.fetchall()
    
    print(f"\n📊 Datos:")
    print(f"   👨‍🔬 Investigadores: {len(researchers)}")
    print(f"   📚 Publicaciones con autores: {len(publications)}")
    
    # 3. Limpiar tabla de relaciones existentes
    cursor.execute("DELETE FROM investigador_publicacion")
    print(f"\n🗑️  Limpiando relaciones existentes...")
    
    # 4. Hacer matching
    print(f"\n🔄 Haciendo matching...")
    print("-" * 80)
    
    matches_found = 0
    total_checks = 0
    
    for pub_id, titulo, autores in publications:
        # Extraer nombres individuales
        author_names = extract_individual_names(autores)
        
        if not author_names:
            continue
        
        for res_id, res_name in researchers:
            total_checks += 1
            
            # Normalizar nombres
            res_name_norm = normalize_name(res_name)
            
            # Verificar si el investigador está en la lista de autores
            for author in author_names:
                author_norm = normalize_name(author)
                
                # Calcular similitud
                score = similarity(res_name_norm, author_norm)
                
                # Si hay match (>80% similitud)
                if score > 0.8:
                    # Verificar que no exista ya
                    cursor.execute("""
                        SELECT id FROM investigador_publicacion 
                        WHERE member_id = ? AND publicacion_id = ?
                    """, (res_id, pub_id))
                    
                    if not cursor.fetchone():
                        # Insertar relación
                        cursor.execute("""
                            INSERT INTO investigador_publicacion 
                            (member_id, publicacion_id, match_score, match_method)
                            VALUES (?, ?, ?, ?)
                        """, (res_id, pub_id, int(score * 100), 'fuzzy_auto'))
                        
                        matches_found += 1
                        
                        if matches_found <= 10:
                            print(f"✅ {res_name} ↔ {titulo[:50]}... ({score:.1%})")
                        elif matches_found % 20 == 0:
                            print(f"   ... {matches_found} matches encontrados ...")
    
    conn.commit()
    
    # 5. Estadísticas finales
    cursor.execute("SELECT COUNT(*) FROM investigador_publicacion")
    total_matches = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT member_id) 
        FROM investigador_publicacion
    """)
    researchers_matched = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT publicacion_id) 
        FROM investigador_publicacion
    """)
    publications_matched = cursor.fetchone()[0]
    
    conn.close()
    
    # 6. Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Total de matches:           {total_matches}")
    print(f"👨‍🔬 Investigadores vinculados:  {researchers_matched}/{len(researchers)} ({researchers_matched/len(researchers)*100:.1f}%)")
    print(f"📚 Publicaciones vinculadas:   {publications_matched}/{len(publications)} ({publications_matched/len(publications)*100:.1f}%)")
    print(f"🔍 Comparaciones realizadas:   {total_checks:,}")
    
    print("\n💡 Próximos pasos:")
    print("   1. Revisa las relaciones en la API")
    print("   2. Ejecuta auditoría de compliance: python3 scripts/audit_compliance.py")
    print("   3. Genera reportes")

if __name__ == "__main__":
    match_researchers_to_publications()
