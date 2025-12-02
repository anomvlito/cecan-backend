from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import sqlite3
from config import DB_PATH

router = APIRouter(prefix="/catalogs", tags=["Catalogs"])

# Static color map for WPs to ensure consistency
WP_COLORS = {
    1: "#FF5733", # Red-ish
    2: "#33FF57", # Green-ish
    3: "#3357FF", # Blue-ish
    4: "#F333FF", # Magenta-ish
    5: "#FF33F3", # Pink-ish
    # Add more if needed or use a generator
}

@router.get("/working-packages")
async def get_working_packages():
    """
    Get list of Working Packages with display colors.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, nombre FROM wps ORDER BY id ASC")
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            wp_id = row["id"]
            # Default color if not in map
            color = WP_COLORS.get(wp_id, "#808080") 
            
            results.append({
                "id": wp_id,
                "name": row["nombre"],
                "color": color
            })
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching WPs: {str(e)}")
    finally:
        conn.close()
