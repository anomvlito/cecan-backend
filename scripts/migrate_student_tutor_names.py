import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

INPUT_FILE = "data/cecan_personnel_normalized.xlsx"

def add_columns_and_sync():
    db = SessionLocal()
    try:
        print("🛠️ Agregando columnas de texto para Tutor y Co-Tutor...")
        
        # 1. Agregar columnas si no existen
        try:
            db.execute(text("ALTER TABLE students ADD COLUMN tutor_name VARCHAR(255)"))
            print("✅ Columna tutor_name agregada.")
        except Exception:
            print("⚠️ Columna tutor_name ya existe o error al agregar.")
            
        try:
            db.execute(text("ALTER TABLE students ADD COLUMN co_tutor_name VARCHAR(255)"))
            print("✅ Columna co_tutor_name agregada.")
        except Exception:
            print("⚠️ Columna co_tutor_name ya existe o error al agregar.")
        
        db.commit()

        # 2. Leer Excel y poblar las columnas de texto
        print(f"📖 Cargando datos de texto desde {INPUT_FILE}...")
        df = pd.read_excel(INPUT_FILE, sheet_name='students')
        
        for _, row in df.iterrows():
            st_name = str(row['full_name']).strip()
            t_name = str(row.get('tutor_name', ''))
            ct_name = str(row.get('co_tutor_name', ''))
            
            if t_name == 'nan': t_name = None
            if ct_name == 'nan': ct_name = None
            
            # Limpiar nombres de cosas como (wp4)
            import re
            def clean(n):
                if not n: return n
                return re.sub(r'\(.*?\)', '', n).strip()
            
            t_name = clean(t_name)
            ct_name = clean(ct_name)

            db.execute(text("""
                UPDATE students 
                SET tutor_name = :t_name, co_tutor_name = :ct_name
                WHERE full_name = :st_name
            """), {"t_name": t_name, "ct_name": ct_name, "st_name": st_name})
            
        db.commit()
        print("✨ Datos de texto sincronizados exitosamente.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_columns_and_sync()
