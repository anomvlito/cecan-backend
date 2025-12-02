import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    # Fallback if config not found
    DB_PATH = "backend/cecan.db"

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # List of new columns to add
    new_columns = [
        ("cargo_oficial", "TEXT"),
        ("url_foto", "TEXT"),
        ("active_projects", "BOOLEAN DEFAULT 1"),
        ("citaciones_totales", "INTEGER"),
        ("indice_h", "INTEGER"),
        ("publicaciones_recientes", "TEXT") # JSON string
    ]

    # Get existing columns to avoid errors
    cursor.execute("PRAGMA table_info(Investigadores)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            print(f"Adding column {col_name} ({col_type})...")
            try:
                cursor.execute(f"ALTER TABLE Investigadores ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")

    conn.commit()

    # Create Publicaciones table if not exists
    print("Checking Publicaciones table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Publicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            fecha TEXT,
            autores TEXT,
            categoria TEXT,
            url_origen TEXT,
            path_pdf_local TEXT,
            contenido_texto TEXT
        )
    """)
    print("Publicaciones table checked/created.")

    # Create Investigador_Publicacion table if not exists
    print("Checking Investigador_Publicacion table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Investigador_Publicacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigador_id INTEGER,
            publicacion_id INTEGER,
            match_score INTEGER,
            match_method TEXT,
            FOREIGN KEY(investigador_id) REFERENCES Investigadores(id),
            FOREIGN KEY(publicacion_id) REFERENCES Publicaciones(id)
        )
    """)
    print("Investigador_Publicacion table checked/created.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
