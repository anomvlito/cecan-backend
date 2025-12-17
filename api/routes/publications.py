"""
Publication Routes for CECAN Platform
API endpoints for publications and data management
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import sqlite3
import threading
from datetime import datetime

from database.session import get_db
from api.routes.auth import require_editor, get_current_user, User
from config import DB_PATH
from services import scraper_service, compliance_service, publication_service
from core.models import Publication

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


@router.post("/audit")
async def run_audit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Trigger full compliance audit.
    Requires Editor role.
    """
    try:
        compliance_service.run_full_audit(db)
        return {"status": "completed", "message": "Audit completed successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/audit/reset")
async def reset_audit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Reset compliance audit status for all publications.
    Requires Editor role.
    """
    try:
        compliance_service.reset_audit_status(db)
        return {"status": "completed", "message": "Audit status reset successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Upload a PDF publication and extract its text content.
    Requires Editor role.
    """
    try:
        # Read file content
        content = await file.read()
        
        # Validate PDF
        is_valid, error_msg = publication_service.validate_pdf_file(file.filename, content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Extract text from PDF
        extracted_text = publication_service.extract_text_from_pdf(content)
        
        # Create new publication
        new_pub = Publication(
            titulo=file.filename,
            autores="Desconocido (PDF Upload)",
            fecha=str(datetime.now().year),
            contenido_texto=extracted_text if extracted_text else "(Sin texto extraíble - PDF escaneado)",
            has_funding_ack=False,
            anid_report_status="Pending"
        )
        
        db.add(new_pub)
        db.commit()
        db.refresh(new_pub)
        
        return {
            "id": new_pub.id,
            "status": "success",
            "filename": file.filename,
            "text_extracted": len(extracted_text) > 0,
            "message": "PDF cargado correctamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")


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
