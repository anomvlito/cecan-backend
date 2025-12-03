import sqlite3
import json
from config import DB_PATH

def test_researchers_query():
    print("Testing Researchers Query...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT 
                am.id, 
                am.full_name, 
                rd.url_foto as photo_url, 
                rd.category, 
                wp.nombre as wp_name,
                rd.indice_h as h_index,
                rd.citaciones_totales as total_citations
            FROM academic_members am
            LEFT JOIN researcher_details rd ON am.id = rd.member_id
            LEFT JOIN wps wp ON am.wp_id = wp.id
            WHERE am.member_type = 'researcher' AND am.is_active = 1
            LIMIT 5
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        researchers_map = {}
        for row in rows:
            researchers_map[row["id"]] = {
                "id": row["id"],
                "full_name": row["full_name"],
                "publications": []
            }
            
        if researchers_map:
            researcher_ids = list(researchers_map.keys())
            placeholders = ",".join("?" * len(researcher_ids))
            
            pub_query = f"""
                SELECT 
                    ip.member_id,
                    p.id,
                    p.titulo as title,
                    p.fecha as year,
                    p.url_origen as url
                FROM publicaciones p
                JOIN investigador_publicacion ip ON p.id = ip.publicacion_id
                WHERE ip.member_id IN ({placeholders})
            """
            cursor.execute(pub_query, researcher_ids)
            pub_rows = cursor.fetchall()
            
            for pub in pub_rows:
                if pub["member_id"] in researchers_map:
                    researchers_map[pub["member_id"]]["publications"].append({
                        "id": pub["id"],
                        "title": pub["title"][:30] + "...",
                        "year": pub["year"],
                        "url": pub["url"]
                    })
        
        print(json.dumps(list(researchers_map.values()), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def test_publications_query():
    print("\nTesting Publications Query...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT 
                id, 
                titulo as title, 
                fecha as year, 
                url_origen as url
            FROM publicaciones
            LIMIT 5
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        publications_map = {}
        for row in rows:
            publications_map[row["id"]] = {
                "id": row["id"],
                "title": row["title"][:30] + "...",
                "url": row["url"],
                "authors": []
            }
            
        # For test, just fetch authors for these 5 publications
        pub_ids = list(publications_map.keys())
        placeholders = ",".join("?" * len(pub_ids))
        
        auth_query = f"""
            SELECT 
                ip.publicacion_id,
                am.id,
                am.full_name,
                rd.url_foto as avatar_url
            FROM academic_members am
            JOIN investigador_publicacion ip ON am.id = ip.member_id
            LEFT JOIN researcher_details rd ON am.id = rd.member_id
            WHERE am.member_type = 'researcher' AND ip.publicacion_id IN ({placeholders})
        """
        cursor.execute(auth_query, pub_ids)
        auth_rows = cursor.fetchall()
        
        for auth in auth_rows:
            if auth["publicacion_id"] in publications_map:
                publications_map[auth["publicacion_id"]]["authors"].append({
                    "id": auth["id"],
                    "full_name": auth["full_name"],
                    "avatar_url": auth["avatar_url"]
                })
        
        print(json.dumps(list(publications_map.values()), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_researchers_query()
    test_publications_query()
