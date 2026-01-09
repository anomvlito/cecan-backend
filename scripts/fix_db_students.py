import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

def fix_db_structure():
    db = SessionLocal()
    try:
        print("🛠️ Ajustando estructura de la tabla students...")
        
        # 1. Eliminar y recrear 'program' como VARCHAR (porque ENUM no se puede convertir directamente)
        try:
            print("Eliminando columna program (ENUM)...")
            db.execute(text("ALTER TABLE students DROP COLUMN IF EXISTS program CASCADE"))
            db.commit()
            
            print("Recreando columna program como VARCHAR...")
            db.execute(text("ALTER TABLE students ADD COLUMN program VARCHAR(255)"))
            db.commit()
            print("✅ Columna program convertida a VARCHAR.")
        except Exception as e:
            print(f"⚠️ Error en program: {e}")
            db.rollback()

        # 1b. Eliminar y recrear 'status' como VARCHAR también
        try:
            print("Eliminando columna status (ENUM)...")
            db.execute(text("ALTER TABLE students DROP COLUMN IF EXISTS status CASCADE"))
            db.commit()
            
            print("Recreando columna status como VARCHAR...")
            db.execute(text("ALTER TABLE students ADD COLUMN status VARCHAR(50) DEFAULT 'Activo'"))
            db.commit()
            print("✅ Columna status convertida a VARCHAR.")
        except Exception as e:
            print(f"⚠️ Error en status: {e}")
            db.rollback()

        # 2. Asegurar que existan tutor_name y co_tutor_name
        for col in ["tutor_name", "co_tutor_name"]:
            try:
                db.execute(text(f"ALTER TABLE students ADD COLUMN {col} VARCHAR(255)"))
                db.commit()
                print(f"✅ Columna {col} agregada.")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"⚠️ Columna {col} ya existe.")
                else:
                    print(f"⚠️ Error en {col}: {e}")
                db.rollback()
        
        print("✅ Estructura de tabla students actualizada correctamente.")
        
    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_db_structure()
