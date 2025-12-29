#!/usr/bin/env python3
"""
Script RÁPIDO para importar publicaciones desde PDFs locales
No descarga nada - usa los PDFs que ya tienes en docs/pdfs/
"""
import sqlite3
import sys
import os
from pypdf import PdfReader
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

# Directorio de PDFs
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "pdfs")

def extract_text_from_pdf(filepath):
    """Extrae texto de un PDF"""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"   ⚠️  Error extrayendo texto: {e}")
        return ""

def extract_title_from_text(text):
    """Intenta extraer el título del texto del PDF"""
    # Tomar las primeras líneas que suelen contener el título
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        # El título suele estar en las primeras 3-5 líneas
        title = ' '.join(lines[:3])
        # Limpiar y limitar longitud
        title = re.sub(r'\s+', ' ', title)
        return title[:200]  # Limitar a 200 caracteres
    return "Sin título"

def main():
    print("=" * 80)
    print("📚 IMPORTACIÓN RÁPIDA DE PUBLICACIONES DESDE PDFs LOCALES")
    print("=" * 80)
    
    # Verificar directorio
    if not os.path.exists(PDF_DIR):
        print(f"\n❌ Error: No se encuentra el directorio {PDF_DIR}")
        return
    
    # Listar PDFs
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
    print(f"\n📄 Encontrados {len(pdf_files)} archivos PDF")
    
    if len(pdf_files) == 0:
        print("⚠️  No hay PDFs para procesar")
        return
    
    # Conectar a BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar cuántas publicaciones ya existen
    cursor.execute("SELECT COUNT(*) FROM publicaciones")
    existing_count = cursor.fetchone()[0]
    print(f"📊 Publicaciones existentes en BD: {existing_count}")
    
    if existing_count > 0:
        response = input(f"\n⚠️  Ya hay {existing_count} publicaciones. ¿Continuar de todos modos? (s/n): ")
        if response.lower() != 's':
            print("❌ Cancelado por el usuario")
            conn.close()
            return
    
    print(f"\n🔄 Procesando {len(pdf_files)} PDFs...")
    print("-" * 80)
    
    imported = 0
    skipped = 0
    errors = 0
    
    for i, pdf_file in enumerate(pdf_files, 1):
        filepath = os.path.join(PDF_DIR, pdf_file)
        
        print(f"\n[{i}/{len(pdf_files)}] {pdf_file}")
        
        # Extraer texto
        print("   📖 Extrayendo texto...")
        text = extract_text_from_pdf(filepath)
        
        if not text or len(text) < 100:
            print("   ⚠️  PDF vacío o sin texto extraíble - saltando")
            skipped += 1
            continue
        
        # Extraer título del contenido
        title = extract_title_from_text(text)
        print(f"   📝 Título detectado: {title[:60]}...")
        
        # Verificar si ya existe
        cursor.execute("SELECT id FROM publicaciones WHERE path_pdf_local = ?", (filepath,))
        if cursor.fetchone():
            print("   ⏭️  Ya existe en BD - saltando")
            skipped += 1
            continue
        
        # Insertar en BD
        try:
            cursor.execute("""
                INSERT INTO publicaciones (
                    titulo, fecha, url_origen, path_pdf_local, contenido_texto, categoria,
                    has_valid_affiliation, has_funding_ack, anid_report_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                "",  # fecha - no la tenemos del PDF
                "",  # url_origen - no la tenemos
                filepath,
                text,
                "Científica",
                False,  # has_valid_affiliation - se auditará después
                False,  # has_funding_ack - se auditará después
                'Error'  # anid_report_status - default
            ))
            conn.commit()
            print("   ✅ Importado exitosamente")
            imported += 1
            
        except Exception as e:
            print(f"   ❌ Error insertando en BD: {e}")
            errors += 1
    
    conn.close()
    
    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Importados:  {imported}")
    print(f"⏭️  Saltados:    {skipped}")
    print(f"❌ Errores:     {errors}")
    print(f"📄 Total PDFs:  {len(pdf_files)}")
    print("\n💡 Próximos pasos:")
    print("   1. Verifica los datos: python3 scripts/check_db_status.py")
    print("   2. Ejecuta matching de investigadores: python3 scripts/run_matching.py")
    print("   3. Audita compliance: python3 scripts/audit_compliance.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
