from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from config import DB_PATH
from database.legacy_wrapper import CecanDB

router = APIRouter(prefix="/public", tags=["Public"])

# --- Schemas ---

class PublicResearcherMetrics(BaseModel):
    h_index: Optional[int] = None
    total_citations: Optional[int] = None

class PublicResearcherOut(BaseModel):
    id: int
    full_name: str
    photo_url: Optional[str] = None
    category: Optional[str] = None
    wp_name: Optional[str] = None
    metrics: PublicResearcherMetrics

# --- Endpoints ---

@router.get("/researchers", response_model=List[PublicResearcherOut])
async def get_public_researchers():
    """
    Get public list of researchers with sanitized fields.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Join AcademicMember, ResearcherDetails, and WorkPackage
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
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "full_name": row["full_name"],
                "photo_url": row["photo_url"],
                "category": row["category"],
                "wp_name": row["wp_name"],
                "metrics": {
                    "h_index": row["h_index"],
                    "total_citations": row["total_citations"]
                }
            })
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching researchers: {str(e)}")
    finally:
        conn.close()

@router.get("/graph")
async def get_public_graph():
    """
    Get simplified graph data for public visualization.
    """
    db = CecanDB()
    try:
        data = db.get_graph_data()
        # We could filter sensitive data here if needed, but get_graph_data seems already safe enough for now
        # based on the legacy implementation.
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")
    finally:
        db.close()
