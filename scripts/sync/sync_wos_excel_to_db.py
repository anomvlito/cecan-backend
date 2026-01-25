
import pandas as pd
import psycopg2
import os
import re

# Configuración de conexión
DB_CONFIG = {
    "dbname": "cecan_db",
    "user": "postgres",
    "password": "postgres", # Ajusta si es diferente
    "host": "localhost",
    "port": "5432"
}

EXCEL_FILE = "wos_full_database_v2.xlsx"
import json

# ... (resto de imports)

def clean_val(val):
    if pd.isna(val) or val == "N/A":
        return None
    return str(val).strip()

def clean_json_list(val):
    """Convierte string separado por | en JSON array válido stringified"""
    if pd.isna(val) or val == "N/A":
        return None
    s_val = str(val).strip()
    # Si ya parece una lista JSON (corchetes), dejarlo
    if s_val.startswith("[") and s_val.endswith("]"):
        return s_val
    
    # Separar por pipe |
    items = [x.strip() for x in s_val.split('|') if x.strip()]
    return json.dumps(items)

def clean_json_obj(val):
    """Para ranking category u otros campos que puedan ser JSON"""
    if pd.isna(val) or val == "N/A":
        return None
    s_val = str(val).strip()
    # Si es un string simple, lo convertimos en string JSON válido para asegurar
    # Pero ojo, si la columna espera un Objeto o Array, un string "simple" tal vez falle
    # si no estÃ¡ entre comillas dobles. 
    # Mejor devolverlo tal cual si postgres espera JSONB
    return s_val

def sync_data():
    print("🚀 Iniciando SINCRONIZACIÓN (Excel -> PostgreSQL)...")
    
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ Error: No se encuentra el archivo {EXCEL_FILE}")
        return

    print("📖 Leyendo archivo Excel...")
    try:
        df = pd.read_excel(EXCEL_FILE)
        print(f"✅ Excel cargado: {len(df)} registros encontrados.")
    except Exception as e:
        print(f"❌ Error leyendo Excel: {e}")
        return

    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1. Obtener IDs ya existentes para no duplicar
        print("🔍 Verificando registros existentes en la base de datos...")
        cur.execute("SELECT wos_id FROM wos_journal_mirror;")
        existing_ids = set(row[0] for row in cur.fetchall())
        print(f"   Datos actuales en DB: {len(existing_ids)} registros.")

        # 2. Filtrar nuevos
        new_records = []
        for _, row in df.iterrows():
            try:
                wos_id = int(row.get("ID"))
                if wos_id not in existing_ids:
                    # Preparar tupla para inserción
                    new_records.append((
                        wos_id,
                        clean_val(row.get("Journal Name")),
                        clean_val(row.get("Status")),
                        clean_val(row.get("Best Quartile")),
                        clean_val(row.get("Best Ranking (%)")),
                        clean_val(row.get("JIF")),
                        clean_val(row.get("5-Year JIF")),
                        clean_val(row.get("ISSN")),
                        clean_val(row.get("eISSN")),
                        clean_json_list(row.get("Category")), # AQUI EL CAMBIO
                        clean_val(row.get("Ranking Category")), # Este parece ser TEXTO plano o JSON simple
                        clean_val(row.get("Publisher")),
                        clean_val(row.get("Country")),
                        clean_val(row.get("URL"))
                    ))
            except ValueError:
                continue # ID inválido

        if not new_records:
            print("\n✨ Todo está actualizado. No hay registros nuevos para insertar.")
            return

        print(f"\n⚡ Se encontraron {len(new_records)} registros NUEVOS para insertar.")
        
        # 3. Insertar masivamente
        print("💾 Insertando en base de datos...")
        insert_query = """
        INSERT INTO wos_journal_mirror (
            wos_id, journal_name, status, best_quartile, best_ranking_percent,
            jif, five_year_jif, issn, eissn, categories, ranking_category,
            publisher, country, source_url
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        from psycopg2.extras import execute_batch
        execute_batch(cur, insert_query, new_records, page_size=100)
        
        conn.commit()
        print(f"✅ ¡ÉXITO! {len(new_records)} registros insertados correctamente.")

        # Verificación final
        cur.execute("SELECT COUNT(*) FROM wos_journal_mirror;")
        final_count = cur.fetchone()[0]
        print(f"📊 Total en base de datos ahora: {final_count}")

    except Exception as e:
        print(f"\n❌ Error de Base de Datos: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    sync_data()
