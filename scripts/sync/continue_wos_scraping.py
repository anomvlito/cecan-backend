
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import psycopg2

# Configuración de Conexión a BD
DB_CONFIG = {
    "dbname": "cecan_db",
    "user": "postgres",
    "password": "postgres", # Ajusta si es diferente
    "host": "localhost",
    "port": "5432"
}

# --- CONFIGURACIÓN DE PRODUCCIÓN ---
END_ID = 25300  # Meta final extendida agresivamente
OUTPUT_FILE = "wos_full_database_v2.xlsx"
BASE_URL = "https://wos-journal.info/journalid/{}"
SAVE_INTERVAL = 50
MAX_CONSECUTIVE_EMPTY = 200

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_last_id_from_db():
    """Consulta la base de datos para saber cuál fue el último wos_id procesado."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT MAX(wos_id) FROM wos_journal_mirror;")
        res = cur.fetchone()
        conn.close()
        max_id = res[0]
        if max_id is None:
            return 0
        return max_id
    except Exception as e:
        print(f"❌ Error conectando a la BD: {e}")
        return 0

def load_existing_excel():
    """Carga el Excel existente si existe, devuelve un DataFrame vacío si no."""
    if os.path.exists(OUTPUT_FILE):
        try:
            return pd.read_excel(OUTPUT_FILE)
        except Exception as e:
            print(f"⚠️ Error leyendo Excel existente: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def get_last_id_from_excel():
    """Obtiene el último ID del Excel para no depender solo de la BD."""
    df = load_existing_excel()
    if not df.empty and "ID" in df.columns:
        try:
            return int(df["ID"].max())
        except:
            pass
    return 0

def save_data(new_items, filename):
    if not new_items: return
    try:
        # Cargar lo que ya existe
        existing_df = load_existing_excel()
        new_df = pd.DataFrame(new_items)
        
        # Concatenar
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Eliminar duplicados por si acaso (por ID)
        if "ID" in final_df.columns:
            final_df.drop_duplicates(subset=["ID"], keep="last", inplace=True)
            # Ordenar por ID
            final_df.sort_values(by="ID", inplace=True)
        
        # Columnas oficiales
        cols = [
            "ID", "Journal Name", "Status", "Best Quartile", "Best Ranking (%)", 
            "JIF", "5-Year JIF", "ISSN", "eISSN", 
            "Category", "Ranking Category", "Publisher", "Country", "URL"
        ]
        # Filtrar solo columnas que existen
        final_cols = [c for c in cols if c in final_df.columns]
        final_df = final_df[final_cols]
        
        final_df.to_excel(filename, index=False)
        print(f"💾 [AUTO-SAVE] Total registros ahora: {len(final_df)}")
    except Exception as e:
        print(f"⚠️ Error guardando Excel: {e}")

# --- MAIN ---

last_id_db = get_last_id_from_db()
last_id_excel = get_last_id_from_excel()
last_id = max(last_id_db, last_id_excel)

print(f"📊 Último ID en BD: {last_id_db} | Último ID en Excel: {last_id_excel}")
print(f"⏩ Retomando desde ID: {last_id}")

start_id = last_id + 1
print(f"🚀 Iniciando SCRAPING CONTINUO del ID {start_id} al {END_ID}...")

data_buffer = [] # Buffer temporal para no guardar en cada iteración
consecutive_empty_count = 0
total_found_session = 0

for j_id in range(start_id, END_ID + 1):
    url = BASE_URL.format(j_id)
    
    # Log explícito por cada intento (Redundante como solicitado)
    print(f"🔎 [{j_id}] Buscando en: {url} ... ", end="")

    try:
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            print("❌ Error HTTP/Vacío")
            continue

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. Nombre
        name_div = soup.find('div', class_='title title2')
        journal_name = name_div.get_text(strip=True).replace("»", "").strip() if name_div else "Unknown"
        
        if journal_name == "Unknown" and soup.title:
             journal_name = soup.title.string.split('-')[0].strip()

        # Condición de vacío / no encontrado
        if not journal_name or "Page not found" in journal_name or journal_name == "WOS-Journal.info":
             print("⚠️  Sin datos / Página no encontrada")
             # YA NO PARAMOS, SEGUIMOS BUSCANDO ETERNAMENTE HASTA END_ID
             continue

        # Encontrado
        total_found_session += 1
        print(f"✅ ENCONTRADO: {journal_name}")

        # 2. Extracción de Datos
        raw_data = {}
        titles = soup.find_all('div', class_='title')
        for t in titles:
            clean_label = t.get_text(strip=True).replace(":", "").strip()
            content_div = t.find_next_sibling('div', class_='content')
            if content_div:
                raw_data[clean_label] = content_div

        def get_text(key):
            div = raw_data.get(key)
            return div.get_text(strip=True) if div else "N/A"

        # A. Status
        status = get_text('Status in WoS core')

        # B. Ranking y Cuartil
        ranking_div = raw_data.get('Best ranking')
        best_quartile = "N/A"
        best_rank_val = "N/A"
        ranking_category = "N/A"
        
        if ranking_div:
            txt = ranking_div.get_text(" ", strip=True)
            match = re.search(r'Percentage rank:\s*([\d\.]+)%', txt)
            if match:
                val = float(match.group(1))
                best_rank_val = f"{val}%"
                if val >= 75: best_quartile = "Q1"
                elif val >= 50: best_quartile = "Q2"
                elif val >= 25: best_quartile = "Q3"
                else: best_quartile = "Q4"
                print(f" -> {best_quartile}", end="")
            
            clean_cat = re.split(r'Percentage rank|║', txt)[0].strip()
            if clean_cat: ranking_category = clean_cat

        # C. Categorías
        cat_div = raw_data.get('Category')
        categories_str = "N/A"
        if cat_div:
            cats = [c.strip() for c in cat_div.get_text(separator="|").split("|") if c.strip()]
            categories_str = " | ".join(cats)

        # D. ISSNs
        issn = get_text('ISSN')
        eissn = get_text('eISSN')

        # E. Publisher (Estrategia Híbrida CrossRef)
        publisher = get_text('Publisher')
        
        # Si no está en el HTML, buscarlo en CrossRef
        if publisher in ["N/A", ""] and (issn != "N/A" or eissn != "N/A"):
            target_issn = issn if issn != "N/A" else eissn
            try:
                # Url pública de CrossRef
                cr_url = f"https://api.crossref.org/journals/{target_issn}"
                cr_r = requests.get(cr_url, timeout=3)
                if cr_r.status_code == 200:
                    cr_data = cr_r.json()
                    publisher = cr_data['message']['publisher']
            except Exception:
                pass 

        # Crear item
        item = {
            "ID": j_id,
            "Journal Name": journal_name,
            "Status": status,
            "Best Quartile": best_quartile,
            "Best Ranking (%)": best_rank_val,
            "JIF": get_text('Journal Impact Factor (JIF)'),
            "5-Year JIF": get_text('5-year Impact Factor'),
            "ISSN": issn,
            "eISSN": eissn,
            "Category": categories_str,
            "Ranking Category": ranking_category,
            "Publisher": publisher,
            "Country": get_text('Country'),
            "URL": url
        }
        
        data_buffer.append(item)
        
        if len(data_buffer) >= SAVE_INTERVAL:
            print("")
            save_data(data_buffer, OUTPUT_FILE)
            data_buffer = [] # Limpiar buffer después de guardar
            
        time.sleep(0.1)

    except Exception as e:
        print(f"\n❌ Error ID {j_id}: {e}")
        time.sleep(1)

    # Log every 50 attempts regardless of success
    if j_id % 50 == 0:
        print(f"\n[INFO] Procesados {j_id - start_id} URLs... (Actual: {j_id})")


print("\n" + "="*50)
# Guardar remanentes
save_data(data_buffer, OUTPUT_FILE)
print("🏁 Proceso finalizado.")

