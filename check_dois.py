import sys
import os
# Add current directory to path so we can import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config

# FORCE CORRECT DB PATH relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_DB_PATH = os.path.join(BASE_DIR, "cecan.db")

print(f"🔍 DEBUG: Ruta base del script: {BASE_DIR}")
print(f"🔍 DEBUG: Ruta calculada de DB: {REAL_DB_PATH}")

# Override config to ensure we use the right one
config.DB_PATH = REAL_DB_PATH

print(f"🔍 DEBUG: Usando base de datos en: {config.DB_PATH}")
if not os.path.exists(config.DB_PATH):
    print(f"⚠️  ALERTA: El archivo de base de datos NO EXISTE en esa ruta.")
else:
    print(f"✅ Archivo encontrado. Tamaño: {os.path.getsize(config.DB_PATH) / (1024*1024):.2f} MB")

from database.session import SessionLocal
from core.models import Publication
from sqlalchemy import func

def check_dois():
    db = SessionLocal()
    try:
        total_pubs = db.query(Publication).count()
        pubs_with_doi = db.query(Publication).filter(Publication.canonical_doi.isnot(None)).count()
        pubs_with_url = db.query(Publication).filter((Publication.url_origen.isnot(None)) & (Publication.url_origen != "")).count()
        
        print("\n" + "="*50)
        print("📊 REPORTE DE ESTADO DE BASE DE DATOS")
        print("="*50)
        print(f"📚 Total de Publicaciones:      {total_pubs}")
        print(f"🔗 Publicaciones con URL:       {pubs_with_url}")
        print(f"🏷️  Publicaciones con DOI (BD): {pubs_with_doi}")
        print("="*50)
        
        if pubs_with_doi > 0:
            print(f"\nLista completa de DOIs encontrados ({pubs_with_doi}):")
            all_pubs = db.query(Publication).filter(Publication.canonical_doi.isnot(None)).order_by(Publication.id).all()
            for p in all_pubs:
                print(f"  - [ID {p.id}] {p.canonical_doi}")
        else:
            print("\n⚠️  No se encontraron DOIs en la columna 'canonical_doi'.")
            
    except Exception as e:
        print(f"❌ Error al consultar la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_dois()
