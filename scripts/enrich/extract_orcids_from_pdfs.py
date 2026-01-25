#!/usr/bin/env python3
"""
Extrae hipervínculos ORCID directamente de los archivos PDF locales.
"""
import os
import re
import sys
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "pdfs")

def extract_orcids():
    print("=" * 80)
    print("🕵️  EXTRAYENDO ORCIDs DE PDFs")
    print("=" * 80)
    
    if not os.path.exists(PDF_DIR):
        print(f"❌ Directorio no encontrado: {PDF_DIR}")
        return

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    print(f"📚 Analizando {len(pdf_files)} archivos PDF...")
    
    total_orcids_found = 0
    files_with_orcid = 0
    
    for filename in pdf_files:
        filepath = os.path.join(PDF_DIR, filename)
        orcids_in_file = set()
        
        try:
            reader = PdfReader(filepath)
            
            for page in reader.pages:
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        if "/A" in obj and "/URI" in obj["/A"]:
                            uri = obj["/A"]["/URI"]
                            # Buscar patrón ORCID en la URI
                            # Formatos: https://orcid.org/0000-0000-0000-0000
                            if "orcid.org" in uri:
                                # Extraer solo el ID
                                match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[\dX])', uri)
                                if match:
                                    orcids_in_file.add(match.group(1))
            
            if orcids_in_file:
                print(f"\n📄 {filename[:50]}...")
                for orcid in orcids_in_file:
                    print(f"   ✅ ORCID encontrado: {orcid}")
                
                total_orcids_found += len(orcids_in_file)
                files_with_orcid += 1
                
        except Exception as e:
            # Algunos PDFs pueden estar encriptados o corruptos, los saltamos silenciosamente
            # print(f"   ⚠️  Error leyendo {filename}: {e}")
            pass

    print("\n" + "=" * 80)
    print("📊 RESUMEN DE EXTRACCIÓN")
    print("=" * 80)
    print(f"   📂 Archivos con ORCIDs: {files_with_orcid}/{len(pdf_files)}")
    print(f"   🆔 Total ORCIDs únicos: {total_orcids_found}")
    print("\n💡 Si esto funciona, el siguiente paso es validar estos IDs con la API de ORCID")

if __name__ == "__main__":
    extract_orcids()
