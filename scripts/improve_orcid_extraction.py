#!/usr/bin/env python3
"""
Extractor de ORCIDs MEJORADO (V2)
Busca tanto en hipervínculos como en el TEXTO PLANO de los PDFs.
"""
import sqlite3
import sys
import os
import re
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "pdfs")

def extract_orcids_v2():
    print("=" * 80)
    print("🕵️  EXTRACCIÓN PROFUNDA DE ORCIDs (Links + Texto)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener publicaciones
    cursor.execute("SELECT id, path_pdf_local, titulo FROM publicaciones WHERE path_pdf_local IS NOT NULL")
    pubs = cursor.fetchall()
    
    print(f"📚 Analizando {len(pubs)} publicaciones...")
    
    updated_count = 0
    total_orcids = 0
    
    # Regex para ORCID (grupos de 4 dígitos separados por guión, último puede ser X)
    orcid_pattern = re.compile(r'\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b')
    
    for pub_id, local_path, titulo in pubs:
        # Resolver path
        if not os.path.isabs(local_path):
            if os.path.basename(local_path) == local_path:
                 pdf_path = os.path.join(PDF_DIR, local_path)
            else:
                 pdf_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), local_path))
        else:
            pdf_path = local_path
            
        if not os.path.exists(pdf_path):
            # Fallback: buscar en PDF_DIR
            filename = os.path.basename(local_path)
            pdf_path = os.path.join(PDF_DIR, filename)
            if not os.path.exists(pdf_path):
                continue

        orcids_found = set()
        
        try:
            reader = PdfReader(pdf_path)
            
            for page in reader.pages:
                # 1. Buscar en Hipervínculos (Metadata)
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        try:
                            obj = annot.get_object()
                            if "/A" in obj and "/URI" in obj["/A"]:
                                uri = obj["/A"]["/URI"]
                                if "orcid.org" in uri:
                                    match = orcid_pattern.search(uri)
                                    if match:
                                        orcids_found.add(match.group(0))
                        except:
                            continue

                # 2. Buscar en Texto Plano (Contenido)
                text = page.extract_text()
                if text:
                    matches = orcid_pattern.findall(text)
                    for m in matches:
                        orcids_found.add(m)
                        
        except Exception as e:
            # print(f"Error en {pdf_path}: {e}")
            pass
            
        if orcids_found:
            # Guardar todos los encontrados, separados por coma
            orcids_str = ",".join(sorted(list(orcids_found)))
            
            # Actualizar BD (sobrescribir o concatenar? Sobrescribimos con la versión más completa)
            cursor.execute("UPDATE publicaciones SET extracted_orcids = ? WHERE id = ?", (orcids_str, pub_id))
            
            updated_count += 1
            total_orcids += len(orcids_found)
            
            # Debug visual para ver qué encuentra
            if len(orcids_found) > 2:
                print(f"   ✨ [{pub_id}] {len(orcids_found)} ORCIDs encontrados")

    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN V2")
    print("=" * 80)
    print(f"   📝 Publicaciones con ORCIDs: {updated_count}/{len(pubs)}")
    print(f"   🆔 Total ORCIDs detectados:  {total_orcids}")
    print("\n💡 Estos ORCIDs ya están guardados en la columna 'extracted_orcids'.")

if __name__ == "__main__":
    extract_orcids_v2()
