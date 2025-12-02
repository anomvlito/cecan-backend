#!/usr/bin/env python3
"""
Fase 1: Preparar BD y Extraer ORCIDs de PDFs
1. Agrega columna 'extracted_orcids' a 'publicaciones'
2. Extrae ORCIDs de los PDFs y los guarda en esa columna
"""
import sqlite3
import sys
import os
import re
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "pdfs")

def setup_database():
    print("=" * 80)
    print("🛠️  PREPARANDO BASE DE DATOS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Agregar extracted_orcids a publicaciones
    cursor.execute("PRAGMA table_info(publicaciones)")
    cols = [c[1] for c in cursor.fetchall()]
    
    if 'extracted_orcids' not in cols:
        print("➕ Agregando columna 'extracted_orcids' a tabla 'publicaciones'...")
        cursor.execute("ALTER TABLE publicaciones ADD COLUMN extracted_orcids TEXT")
    else:
        print("✅ Columna 'extracted_orcids' ya existe en 'publicaciones'")

    # 2. Verificar columna orcid en researcher_details
    cursor.execute("PRAGMA table_info(researcher_details)")
    cols_rd = [c[1] for c in cursor.fetchall()]
    
    if 'orcid' not in cols_rd:
        print("➕ Agregando columna 'orcid' a tabla 'researcher_details'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN orcid TEXT")
    else:
        print("✅ Columna 'orcid' ya existe en 'researcher_details'")
        
    conn.commit()
    conn.close()

def extract_and_save():
    print("\n" + "=" * 80)
    print("🕵️  EXTRAYENDO Y GUARDANDO ORCIDs")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener publicaciones que tienen PDF local
    cursor.execute("SELECT id, path_pdf_local, titulo FROM publicaciones WHERE path_pdf_local IS NOT NULL")
    pubs = cursor.fetchall()
    
    print(f"📚 Procesando {len(pubs)} publicaciones con PDF local...")
    
    updated_count = 0
    total_orcids = 0
    
    for pub_id, local_path, titulo in pubs:
        # El path en BD puede ser relativo o absoluto, aseguramos absoluto
        if not os.path.isabs(local_path):
            # Asumimos que está en docs/pdfs si es solo nombre de archivo
            if os.path.basename(local_path) == local_path:
                 pdf_path = os.path.join(PDF_DIR, local_path)
            else:
                 # Intentar resolver relativo al root del proyecto
                 pdf_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), local_path))
        else:
            pdf_path = local_path
            
        if not os.path.exists(pdf_path):
            # Intentar buscar solo por nombre de archivo en PDF_DIR
            filename = os.path.basename(local_path)
            pdf_path = os.path.join(PDF_DIR, filename)
            if not os.path.exists(pdf_path):
                continue

        orcids_found = set()
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        if "/A" in obj and "/URI" in obj["/A"]:
                            uri = obj["/A"]["/URI"]
                            if "orcid.org" in uri:
                                match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[\dX])', uri)
                                if match:
                                    orcids_found.add(match.group(1))
        except Exception:
            pass
            
        if orcids_found:
            orcids_str = ",".join(orcids_found)
            cursor.execute("UPDATE publicaciones SET extracted_orcids = ? WHERE id = ?", (orcids_str, pub_id))
            updated_count += 1
            total_orcids += len(orcids_found)
            if updated_count % 10 == 0:
                print(f"   ✅ Procesadas {updated_count} publicaciones con ORCIDs...")

    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"   📝 Publicaciones actualizadas: {updated_count}")
    print(f"   🆔 Total ORCIDs extraídos: {total_orcids}")
    print("\n💡 Ahora los ORCIDs están seguros en la BD. Podemos validarlos con la API sin prisa.")

if __name__ == "__main__":
    setup_database()
    extract_and_save()
