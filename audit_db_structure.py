import os
import sys
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def audit_db():
    print("🔎 AUDITORIA DE INTEGRIDAD DE BASE DE DATOS")
    print("===========================================")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL no encontrada en .env")
        return

    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            print(f"✅ Conectado a: {db_url.split('@')[1]}") # Hide credentials
            
            # Check 1: Old table (Should be None or strictly legacy)
            print("\n1. Verificando tabla antigua 'publicaciones'...")
            result_old = connection.execute(text("SELECT to_regclass('public.publicaciones');")).scalar()
            if result_old:
                 print(f"⚠️  ALERTA: La tabla 'publicaciones' TODAVIA EXISTE (OID: {result_old}).")
                 print("    (Esto es normal si aún no borramos la tabla vieja, pero cuidado con los zombies).")
            else:
                 print("✅ Tabla 'publicaciones' no existe (Correcto).")

            # Check 2: New table (Should exist)
            print("\n2. Verificando tabla nueva 'publications'...")
            result_new = connection.execute(text("SELECT to_regclass('public.publications');")).scalar()
            
            if not result_new:
                print("❌ FATAL: La tabla 'publications' NO EXISTE.")
                print("   -> Debes correr 'alembic upgrade head'.")
                return
            else:
                print(f"✅ Tabla 'publications' encontrada (OID: {result_new}).")

            # Check 3: Columns
            print("\n3. Verificando columnas en 'publications'...")
            insp = inspect(engine)
            columns = [c['name'] for c in insp.get_columns('publications')]
            
            required_map = {
                'title': 'titulo',
                'year': 'fecha',
                'content': 'contenido_texto'
            }
            
            failures = []
            
            if 'title' in columns:
                print("✅ Columna 'title' encontrada.")
            else:
                print("❌ FALTA Columna 'title'.")
                failures.append('title')
                
            if 'titulo' in columns:
                print("⚠️  ALERTA: Columna 'titulo' (Legacy) todavía existe.")
            
            if not failures:
                print("\n🎉 RESULTADO FINAL: ESTRUCTURA DE BD CORRECTA (PASA)")
            else:
                print(f"\n🚫 RESULTADO FINAL: NO PASA (Faltan: {failures})")

    except Exception as e:
        print(f"\n❌ ERROR DE EJECUCIÓN: {e}")

if __name__ == "__main__":
    audit_db()
