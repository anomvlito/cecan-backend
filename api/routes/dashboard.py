"""
General/Dashboard Routes for CECAN Platform
API endpoints for metrics, graph data, and dashboard statistics
"""

from fastapi import APIRouter, Depends
import sqlite3

from api.routes.auth import get_current_user, User
from config import DB_PATH
from database.legacy_wrapper import CecanDB

router = APIRouter(tags=["Dashboard"])


@router.get("/metrics")
async def get_metrics(current_user: User = Depends(get_current_user)):
    """Returns aggregated metrics for the Indicators dashboard"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total publications
    cursor.execute("SELECT COUNT(*) as total FROM publicaciones")
    total_pubs = cursor.fetchone()['total']
    
    # Total citations
    cursor.execute("SELECT SUM(citaciones_totales) as total FROM researcher_details")
    total_citations = cursor.fetchone()['total'] or 0
    
    # Average H-index
    cursor.execute("SELECT AVG(indice_h) as avg FROM researcher_details WHERE indice_h IS NOT NULL AND indice_h > 0")
    avg_hindex = cursor.fetchone()['avg'] or 0
    
    # Total investigators
    cursor.execute("SELECT COUNT(*) as total FROM academic_members WHERE member_type='researcher'")
    total_investigators = cursor.fetchone()['total']
    
    conn.close()
    
    return {
        "total_publicaciones": total_pubs,
        "total_citas": int(total_citations),
        "indice_h_promedio": round(avg_hindex, 1),
        "total_investigadores": total_investigators
    }


@router.get("/graph-data")
async def get_graph_data(current_user: User = Depends(get_current_user)):
    """Returns the graph data (nodes and edges) for network visualization"""
    db = CecanDB()
    try:
        db.connect()
        data = db.get_graph_data()
        return data
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")
    finally:
        db.close()
