
import pandas as pd
import sys
import os

# Ruta ajustada para el entorno WSL
file_path = "/home/fabian/src/cecan-proyect/archivado/Cartas Gantt FINALES e informadas/WP-5 Carta Gantt 2025 lista BN-CCV.xlsx"

try:
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        # Listemos el directorio padre para ver qué hay si falla
        parent_dir = os.path.dirname(file_path)
        if os.path.exists(parent_dir):
            print(f"Listing contents of {parent_dir}:")
            print(os.listdir(parent_dir))
        else:
            print(f"Directory {parent_dir} also does not exist.")
        sys.exit(1)

    # Intentar leer el excel
    print(f"Reading file: {file_path}")
    df = pd.read_excel(file_path)
    
    print("\n=== COLUMNS ===")
    print(df.columns.tolist())
    
    print("\n=== FIRST 20 ROWS ===")
    print(df.head(20).to_string())
    
    # Intentar inferir estructura
    print("\n=== DATA STRUCTURE ANALYSIS ===")
    print(f"Total Rows: {len(df)}")
    
except ImportError:
    print("Error: pandas or openpyxl not installed. We need 'pip install pandas openpyxl'")
except Exception as e:
    print(f"An error occurred: {e}")
