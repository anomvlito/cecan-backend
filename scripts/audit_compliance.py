#!/usr/bin/env python3
"""
Auditoría de Compliance: Verifica si las publicaciones mencionan a CECAN/FONDAP
"""
import sqlite3
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def audit_compliance():
    print("=" * 80)
    print("🕵️  AUDITORÍA DE COMPLIANCE (FONDAP/CECAN)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener publicaciones con texto
    cursor.execute("SELECT id, titulo, contenido_texto FROM publicaciones")
    publications = cursor.fetchall()
    
    print(f"📚 Analizando {len(publications)} publicaciones...")
    print("-" * 80)
    
    keywords = {
        'FONDAP': r'FONDAP|1523A0004',
        'CECAN': r'CECAN|Centro para la Prevención',
        'ANID': r'ANID|Agencia Nacional'
    }
    
    stats = {k: 0 for k in keywords}
    fully_compliant = 0
    
    updates = []
    
    for pub_id, titulo, texto in publications:
        if not texto:
            continue
            
        texto_upper = texto.upper()
        mentions = []
        is_compliant = False
        
        # Verificar keywords
        has_fondap = bool(re.search(keywords['FONDAP'], texto_upper))
        has_cecan = bool(re.search(keywords['CECAN'], texto_upper))
        
        if has_fondap: stats['FONDAP'] += 1
        if has_cecan: stats['CECAN'] += 1
        if 'ANID' in texto_upper: stats['ANID'] += 1
        
        # Regla de negocio: Debe tener FONDAP o el código del proyecto
        if has_fondap or has_cecan:
            is_compliant = True
            fully_compliant += 1
            mentions.append("✅ COMPLIANT")
        else:
            mentions.append("❌ MISSING ACK")
            
        # Guardar para actualizar BD
        updates.append((is_compliant, pub_id))
        
    # Actualizar BD en lote
    cursor.executemany("""
        UPDATE publicaciones 
        SET has_funding_ack = ?, 
            anid_report_status = CASE WHEN ? THEN 'Compliant' ELSE 'Review' END
        WHERE id = ?
    """, [(x[0], x[0], x[1]) for x in updates])
    
    conn.commit()
    conn.close()
    
    # Reporte
    print(f"\n📊 RESULTADOS DE AUDITORÍA")
    print(f"   ✅ Cumplen (Mencionan FONDAP/CECAN): {fully_compliant}/{len(publications)} ({fully_compliant/len(publications)*100:.1f}%)")
    print(f"   ❌ No cumplen (Posible falta de Ack): {len(publications) - fully_compliant}")
    
    print("\n🔍 DETALLE POR KEYWORD:")
    for key, count in stats.items():
        print(f"   • {key}: {count} publicaciones")

if __name__ == "__main__":
    audit_compliance()
