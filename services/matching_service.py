import sqlite3
import re
from thefuzz import fuzz
from config import DB_PATH

def normalize_text(text):
    if not text: return ""
    return text.lower().strip()

def match_researchers():
    print("Starting researcher-publication matching...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Get all Researchers
    cursor.execute("SELECT id, nombre FROM Investigadores")
    researchers = [dict(row) for row in cursor.fetchall()]
    
    # 2. Get all Publications with text content
    cursor.execute("SELECT id, titulo, contenido_texto FROM Publicaciones WHERE contenido_texto IS NOT NULL AND contenido_texto != ''")
    publications = [dict(row) for row in cursor.fetchall()]
    
    matches_found = 0
    
    for pub in publications:
        pub_id = pub['id']
        # Use first 3000 chars for matching (usually contains title and authors)
        content_sample = pub['contenido_texto'][:3000]
        title = pub['titulo']
        
        # Combine title and content for better matching context
        search_text = f"{title}\n{content_sample}"
        
        for researcher in researchers:
            res_id = researcher['id']
            name = researcher['nombre']
            
            # Skip if name is too short to be unique
            if len(name) < 5: continue
            
            match_score = 0
            match_method = None
            
            # Method A: Exact Match (Case Insensitive)
            if name.lower() in search_text.lower():
                match_score = 100
                match_method = "exact"
            
            # Method B: Regex for "Lastname, Initial" or "Initial. Lastname"
            # Split name into parts
            parts = name.split()
            if not match_method and len(parts) >= 2:
                last_name = parts[-1]
                first_initial = parts[0][0]
                
                # Pattern 1: F. Lastname (e.g., P. Margozzini)
                p1 = rf"{first_initial}\.?\s+{last_name}"
                # Pattern 2: Lastname, F. (e.g., Margozzini, P.)
                p2 = rf"{last_name},?\s+{first_initial}\.?"
                
                if re.search(p1, search_text, re.IGNORECASE) or re.search(p2, search_text, re.IGNORECASE):
                    match_score = 90
                    match_method = "regex_initials"

            # Method C: Fuzzy Match
            if not match_method:
                # We check if the name is "partially" in the text with high similarity
                # Partial ratio is good for finding substrings
                score = fuzz.partial_ratio(name.lower(), search_text.lower())
                if score >= 85:
                    match_score = score
                    match_method = "fuzzy"
            
            if match_score > 0:
                # Check if match already exists to avoid duplicates
                cursor.execute("""
                    SELECT id FROM Investigador_Publicacion 
                    WHERE investigador_id = ? AND publicacion_id = ?
                """, (res_id, pub_id))
                
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO Investigador_Publicacion (investigador_id, publicacion_id, match_score, match_method)
                        VALUES (?, ?, ?, ?)
                    """, (res_id, pub_id, match_score, match_method))
                    matches_found += 1
                    print(f"Match found: {name} -> {title[:30]}... ({match_method}: {match_score})")

    conn.commit()
    conn.close()
    print(f"Matching complete. Found {matches_found} new links.")
    return matches_found

if __name__ == "__main__":
    match_researchers()
