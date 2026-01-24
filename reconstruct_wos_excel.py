
import pandas as pd
import psycopg2
import os

# Configuración de conexión
DB_CONFIG = {
    "dbname": "cecan_db",
    "user": "postgres",
    "password": "postgres", # Ajusta si es diferente
    "host": "localhost",
    "port": "5432"
}
OUTPUT_FILE = "wos_full_database_v2.xlsx"

def reconstruct_excel():
    print("🚀 Iniciando reconstrucción del Excel desde la Base de Datos...")
    
    conn = None
    try:
        # Conectar directamente con psycopg2
        print("🔌 Conectando a PostgreSQL...")
        conn = psycopg2.connect(**DB_CONFIG)
        
        # Query SQL
        query = """
        SELECT 
            wos_id,
            journal_name,
            status,
            best_quartile,
            best_ranking_percent,
            jif,
            five_year_jif,
            issn,
            eissn,
            categories,
            ranking_category,
            publisher,
            country,
            source_url
        FROM wos_journal_mirror
        ORDER BY wos_id ASC;
        """
        
        print("📥 Descargando datos...")
        # Usar pandas con la conexión cruda de psycopg2 o cursor
        # Para máxima compatibilidad, usaremos cursor + fetchall
        with conn.cursor() as cursor:
            cursor.execute(query)
            # Obtener nombres de columnas
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            
        if not data:
            print("⚠️ ADVERTENCIA: La consulta no devolvió resultados.")
            return

        # Crear DataFrame
        df = pd.DataFrame(data, columns=columns)
        
        # Renombrar columnas para coincidir con el Excel original (Mapeo manual)
        column_mapping = {
            "wos_id": "ID",
            "journal_name": "Journal Name",
            "status": "Status",
            "best_quartile": "Best Quartile",
            "best_ranking_percent": "Best Ranking (%)",
            "jif": "JIF",
            "five_year_jif": "5-Year JIF",
            "issn": "ISSN",
            "eissn": "eISSN",
            "categories": "Category",
            "ranking_category": "Ranking Category",
            "publisher": "Publisher",
            "country": "Country",
            "source_url": "URL"
        }
        df.rename(columns=column_mapping, inplace=True)

        print(f"✅ Se recuperaron {len(df)} registros.")

        print(f"💾 Guardando archivo Excel: {OUTPUT_FILE}...")
        df.to_excel(OUTPUT_FILE, index=False)
        
        print("\n" + "="*50)
        print("🎉 ¡Excel reconstruido exitosamente!")
        print(f"📍 Archivo guardado en: {os.path.abspath(OUTPUT_FILE)}")
        print("="*50)

    except Exception as e:
        print(f"\n❌ Ocurrió un error: {e}")
        print("Asegúrate de tener instalada la librería: psycopg2 (o psycopg2-binary) y pandas")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reconstruct_excel()
