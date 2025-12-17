from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from config import DB_PATH
from config import DB_PATH
from database.legacy_wrapper import CecanDB
from schemas import PublicationSummarySchema, ResearcherSummarySchema

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
    publications: List[PublicationSummarySchema] = []

class PublicPublicationOut(BaseModel):
    id: int
    title: str
    year: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    has_funding_ack: bool = False
    anid_report_status: str = "Pending"
    authors: List[ResearcherSummarySchema] = []

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
        
        researchers_map = {}
        for row in rows:
            researchers_map[row["id"]] = {
                "id": row["id"],
                "full_name": row["full_name"],
                "photo_url": row["photo_url"],
                "category": row["category"],
                "wp_name": row["wp_name"],
                "metrics": {
                    "h_index": row["h_index"],
                    "total_citations": row["total_citations"]
                },
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
                    p.url_origen as url,
                    p.has_funding_ack,
                    p.anid_report_status
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
                        "title": pub["title"],
                        "year": pub["year"],
                        "url": pub["url"],
                        "has_funding_ack": bool(pub["has_funding_ack"]) if pub["has_funding_ack"] is not None else False,
                        "anid_report_status": pub["anid_report_status"] or "Pending"
                    })
        
        return list(researchers_map.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching researchers: {str(e)}")
    finally:
        conn.close()

@router.get("/publications", response_model=List[PublicPublicationOut])
async def get_public_publications():
    """
    Get public list of publications with authors.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Fetch all publications
        query = """
            SELECT 
                id, 
                titulo as title, 
                fecha as year, 
                url_origen as url,
                has_funding_ack,
                anid_report_status
            FROM publicaciones
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        publications_map = {}
        for row in rows:
            publications_map[row["id"]] = {
                "id": row["id"],
                "title": row["title"],
                "year": row["year"],
                "url": row["url"],
                "has_funding_ack": bool(row["has_funding_ack"]) if row["has_funding_ack"] is not None else False,
                "anid_report_status": row["anid_report_status"] or "Pending",
                "authors": []
            }
            
        # Fetch all author connections
        auth_query = """
            SELECT 
                ip.publicacion_id,
                am.id,
                am.full_name,
                rd.url_foto as avatar_url
            FROM academic_members am
            JOIN investigador_publicacion ip ON am.id = ip.member_id
            LEFT JOIN researcher_details rd ON am.id = rd.member_id
            WHERE am.member_type = 'researcher'
        """
        cursor.execute(auth_query)
        auth_rows = cursor.fetchall()
        
        for auth in auth_rows:
            if auth["publicacion_id"] in publications_map:
                publications_map[auth["publicacion_id"]]["authors"].append({
                    "id": auth["id"],
                    "full_name": auth["full_name"],
                    "avatar_url": auth["avatar_url"]
                })
        
        return list(publications_map.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching publications: {str(e)}")
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
