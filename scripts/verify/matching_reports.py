#!/usr/bin/env python3
"""
Genera reportes de matching investigadores-publicaciones
SIN crear tablas nuevas - usa las existentes
"""
import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def generate_matching_reports():
    """
    Genera reportes útiles del matching
    """
    print("=" * 80)
    print("📊 REPORTES DE MATCHING")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. TOP 10 INVESTIGADORES MÁS PRODUCTIVOS
    print("\n🏆 TOP 10 INVESTIGADORES MÁS PRODUCTIVOS")
    print("-" * 80)
    cursor.execute("""
        SELECT 
            am.full_name,
            COUNT(ip.publicacion_id) as num_pubs,
            AVG(ip.match_score) as avg_score
        FROM academic_members am
        JOIN investigador_publicacion ip ON am.id = ip.member_id
        GROUP BY am.id
        ORDER BY num_pubs DESC
        LIMIT 10
    """)
    
    for i, (name, count, score) in enumerate(cursor.fetchall(), 1):
        print(f"   {i:2}. {name:40} → {count:3} publicaciones (confianza: {score:.0f}%)")
    
    # 2. INVESTIGADORES SIN PUBLICACIONES
    print("\n\n⚠️  INVESTIGADORES SIN PUBLICACIONES VINCULADAS")
    print("-" * 80)
    cursor.execute("""
        SELECT am.full_name
        FROM academic_members am
        LEFT JOIN investigador_publicacion ip ON am.id = ip.member_id
        WHERE ip.id IS NULL
        ORDER BY am.full_name
        LIMIT 20
    """)
    
    no_pubs = cursor.fetchall()
    print(f"   Total: {len(no_pubs)} investigadores")
    print("\n   Primeros 20:")
    for name, in no_pubs[:20]:
        print(f"      • {name}")
    
    # 3. PUBLICACIONES MÁS COLABORATIVAS
    print("\n\n👥 PUBLICACIONES MÁS COLABORATIVAS (más investigadores)")
    print("-" * 80)
    cursor.execute("""
        SELECT 
            p.titulo,
            COUNT(ip.member_id) as num_researchers
        FROM publicaciones p
        JOIN investigador_publicacion ip ON p.id = ip.publicacion_id
        GROUP BY p.id
        ORDER BY num_researchers DESC
        LIMIT 10
    """)
    
    for i, (titulo, count) in enumerate(cursor.fetchall(), 1):
        print(f"   {i:2}. [{count} autores] {titulo[:70]}...")
    
    # 4. DISTRIBUCIÓN DE CONFIANZA
    print("\n\n📈 DISTRIBUCIÓN DE CONFIANZA EN MATCHES")
    print("-" * 80)
    cursor.execute("""
        SELECT 
            CASE 
                WHEN match_score >= 95 THEN '95-100% (Exacto)'
                WHEN match_score >= 90 THEN '90-94% (Muy alto)'
                WHEN match_score >= 85 THEN '85-89% (Alto)'
                WHEN match_score >= 80 THEN '80-84% (Bueno)'
                ELSE '<80% (Bajo)'
            END as rango,
            COUNT(*) as cantidad
        FROM investigador_publicacion
        GROUP BY rango
        ORDER BY MIN(match_score) DESC
    """)
    
    for rango, cantidad in cursor.fetchall():
        bar = "█" * (cantidad // 5)
        print(f"   {rango:20} {cantidad:3} {bar}")
    
    # 5. RESUMEN EJECUTIVO
    print("\n\n" + "=" * 80)
    print("📋 RESUMEN EJECUTIVO")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM investigador_publicacion")
    total_matches = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT member_id) FROM investigador_publicacion")
    active_researchers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM academic_members")
    total_researchers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT publicacion_id) FROM investigador_publicacion")
    linked_pubs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE autores IS NOT NULL AND autores != ''")
    total_pubs = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(match_score) FROM investigador_publicacion")
    avg_confidence = cursor.fetchone()[0]
    
    print(f"""
    Total de conexiones:        {total_matches}
    Investigadores activos:     {active_researchers}/{total_researchers} ({active_researchers/total_researchers*100:.1f}%)
    Publicaciones vinculadas:   {linked_pubs}/{total_pubs} ({linked_pubs/total_pubs*100:.1f}%)
    Confianza promedio:         {avg_confidence:.1f}%
    
    Promedio pubs/investigador: {total_matches/active_researchers:.1f}
    Promedio autores/pub:       {total_matches/linked_pubs:.1f}
    """)
    
    conn.close()
    
    print("\n💡 Estos datos ya están en la BD - no se crearon tablas nuevas")
    print("   Puedes acceder a ellos desde la API en cualquier momento")

if __name__ == "__main__":
    generate_matching_reports()
