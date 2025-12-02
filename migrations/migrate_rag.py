import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

def migrate_rag():
    print(f"Migrating database for RAG at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create PublicationChunks table
    print("Checking PublicationChunks table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS PublicationChunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publicacion_id INTEGER,
            chunk_index INTEGER,
            content TEXT,
            embedding BLOB, -- Storing embedding as bytes (serialized numpy array or JSON)
            FOREIGN KEY(publicacion_id) REFERENCES Publicaciones(id)
        )
    """)
    print("PublicationChunks table checked/created.")

    conn.commit()
    conn.close()
    print("RAG Migration complete.")

if __name__ == "__main__":
    migrate_rag()
