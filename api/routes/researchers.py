"""
Researcher Routes for CECAN Platform
API endpoints for staff/researchers management
"""

from fastapi import APIRouter, Depends
import sqlite3
import threading

from api.routes.auth import require_editor, get_current_user, User
from config import DB_PATH
from services import scraper_service, matching_service

router = APIRouter(prefix="/researchers", tags=["Researchers"])


@router.get("")
async def get_researchers(current_user: User = Depends(get_current_user)):
    """Get all researchers/staff members"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, nombre, cargo_oficial, url_foto, active_projects,
               citaciones_totales, indice_h, publicaciones_recientes
        FROM Investigadores
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@router.post("/sync")
async def sync_staff(
    current_user: User = Depends(require_editor)
):
    """
    Synchronize staff data from external sources.
    Requires Editor role.
    """
    thread = threading.Thread(target=scraper_service.sync_staff_data)
    thread.start()
    
    return {
        "status": "started",
        "message": "Staff synchronization started in background"
    }


@router.post("/match")
async def run_matching(
    current_user: User = Depends(require_editor)
):
    """
    Run researcher-publication matching algorithm.
    Requires Editor role.
    """
    thread = threading.Thread(target=matching_service.match_researchers)
    thread.start()
    
    return {
        "status": "started",
        "message": "Matching process started in background"
    }
