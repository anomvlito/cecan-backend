
import sys
import os
from sqlalchemy import create_engine, inspect
from fastapi.testclient import TestClient

# Adjust path to include backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

try:
    from main import app
    from core.config import settings
except ImportError as e:
    print(f"Error importando módulos del backend: {e}")
    sys.exit(1)

def check_database_columns():
    print("--- Verificando columnas en Base de Datos ---")
    try:
        # Construct DB URL from settings, handling sqlite relative path if needed
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///./"):
             # Fix relative path for sqlite if running from a different dir
             db_path = os.path.join(backend_dir, db_url.replace("sqlite:///./", ""))
             db_url = f"sqlite:///{db_path}"
        
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Check 'publications' table
        if inspector.has_table('publications'):
            pub_columns = [col['name'] for col in inspector.get_columns('publications')]
            required_pub_fields = ['canonical_doi', 'is_auditable', 'last_openalex_sync']
            
            missing_pub = [field for field in required_pub_fields if field not in pub_columns]
            
            if missing_pub:
                print(f"❌ Faltan columnas en 'publications': {missing_pub}")
            else:
                print("✅ Todas las columnas nuevas existen en 'publications'.")
        else:
            print("❌ La tabla 'publications' no existe.")

    except Exception as e:
        print(f"❌ Error conectando a BD: {e}")

def check_api_fields():
    print("\n--- Verificando campos en API Response ---")
    try:
        client = TestClient(app)
        response = client.get("/api/researchers")
        
        if response.status_code != 200:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return

        data = response.json()
        if not data:
            print("⚠️ Endpoint respondió OK pero la lista está vacía (no hay datos para verificar campos).")
            return

        # Check first researcher
        first_researcher = data[0]
        print(f"Investigador ID: {first_researcher.get('id')}")
        
        # Check if publications are included and have the fields
        # Note: The structure depends on the schema. If verification fails I'll print the structure.
        if 'publications' in first_researcher:
            pubs = first_researcher['publications']
            if pubs:
                first_pub = pubs[0]
                expected_fields = ['canonical_doi', 'is_auditable', 'last_openalex_sync']
                missing_fields = [f for f in expected_fields if f not in first_pub]
                
                if missing_fields:
                    print(f"❌ Faltan campos en la publicación (API): {missing_fields}")
                    print(f"Campos disponibles: {list(first_pub.keys())}")
                else:
                    print("✅ Los campos nuevos están presentes en la respuesta de la API (Publicaciones).")
            else:
                print("⚠️ El investigador no tiene publicaciones.")
        else:
             print("⚠️ El campo 'publications' no está en la respuesta del investigador.")

    except Exception as e:
        print(f"❌ Error probando API: {e}")

if __name__ == "__main__":
    check_database_columns()
    check_api_fields()
