"""
Publication Routes for CECAN Platform
API endpoints for publications and data management
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import sqlite3
import threading

from database.session import get_db
from api.routes.auth import require_editor, get_current_user, User
from config import DB_PATH
from services import scraper_service

router = APIRouter(prefix="/publications", tags=["Publications"])


@router.get("")
async def get_publications(current_user: User = Depends(get_current_user)):
    """Get all publications with researcher matches"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM Publicaciones ORDER BY id DESC")
    pubs = [dict(row) for row in cursor.fetchall()]
    
    for pub in pubs:
        cursor.execute("""
            SELECT i.nombre, ip.match_score, ip.match_method
            FROM Investigador_Publicacion ip
            JOIN Investigadores i ON ip.investigador_id = i.id
            WHERE ip.publicacion_id = ?
        """, (pub['id'],))
        matches = [dict(row) for row in cursor.fetchall()]
        pub['investigadores_relacionados'] = matches
        
    conn.close()
    return pubs


@router.post("/sync")
async def sync_publications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Synchronize publications from external sources.
    Requires Editor role.
    """
    # Run in background
    thread = threading.Thread(target=scraper_service.sync_publications_data)
    thread.start()
    
    return {
        "status": "started",
        "message": "Publications synchronization started in background"
    }


@router.post("/{pub_id}/summary")
async def generate_summary(
    pub_id: int
):
    """Generate AI summary for a publication"""
    from services.agent_service import CecanAgent
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM Publicaciones WHERE id = ?", (pub_id,))
    pub = cursor.fetchone()
   
    if not pub:
        conn.close()
        return {"error": "Publication not found"}
    
    text = pub['contenido_texto'] or pub['resumen']
    
    if not text:
        conn.close()
        return {"error": "No content available"}
    
    agent = CecanAgent()
    prompt = f"Resume en 3-4 oraciones clave este artículo: {text[:2000]}"
    summary = agent.send_message(prompt)
    agent.close()
    
    cursor.execute("UPDATE Publicaciones SET summary_ai = ? WHERE id = ?", (summary, pub_id))
    conn.commit()
    conn.close()
    
    return {"summary": summary}
