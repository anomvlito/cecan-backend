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
    Upload a PDF publication with intelligent data enrichment.
    Automatically detects DOI, matches authors, and generates summaries.
    Requires Editor role.
    """
    try:
        # Read file content
        content = await file.read()
        
        # Validate PDF
        is_valid, error_msg = publication_service.validate_pdf_file(file.filename, content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Enrich publication data (DOI, authors, summaries)
        enriched_data = publication_service.enrich_publication_data(content, file.filename, db)
        
        # Prepare author names string
        author_names = []
        if enriched_data["matched_author_ids"]:
            from core.models import AcademicMember
            authors = db.query(AcademicMember).filter(
                AcademicMember.id.in_(enriched_data["matched_author_ids"])
            ).all()
            author_names = [a.full_name for a in authors]
        
        autores_str = ", ".join(author_names) if author_names else "Autores no identificados"
        
        # Extract clean title from filename
        clean_title = file.filename.replace('.pdf', '').replace('_', ' ')
        
        # Create new publication with enriched data
        new_pub = Publication(
            titulo=clean_title,
            autores=autores_str,
            fecha=str(datetime.now().year),
            url_origen=enriched_data["doi_url"],  # DOI URL if found
            contenido_texto=enriched_data["text"] if enriched_data["text"] else "(Sin texto extraíble)",
            resumen_es=enriched_data["resumen_es"],
            resumen_en=enriched_data["resumen_en"],
            has_funding_ack=False,
            anid_report_status="Pending"
        )
        
        db.add(new_pub)
        db.commit()
        db.refresh(new_pub)
        
        # Create researcher-publication connections
        from core.models import ResearcherPublication
        for author_id in enriched_data["matched_author_ids"]:
            connection = ResearcherPublication(
                member_id=author_id,
                publicacion_id=new_pub.id,
                match_score=100,
                match_method="text_match"
            )
            db.add(connection)
        
        db.commit()
        
        # ✅ NUEVO: Indexar en RAG inmediatamente
        from services.rag_service import get_semantic_engine
        
        rag_result = {"success": False, "chunks_created": 0}
        if enriched_data["text"] and len(enriched_data["text"]) > 100:
            try:
                print(f"   [Upload] Indexing publication {new_pub.id} in RAG...")
                engine = get_semantic_engine()
                rag_result = engine.process_single_publication(new_pub.id)
                
                if rag_result.get("success"):
                    print(f"   [Upload] Successfully indexed publication {new_pub.id}")
                else:
                    print(f"   [Upload] Warning: Failed to index publication {new_pub.id}: {rag_result.get('error')}")
            except Exception as e:
                print(f"   [Upload] Warning: Exception while indexing publication {new_pub.id}: {e}")
                rag_result = {"success": False, "error": str(e), "chunks_created": 0}
        else:
            print(f"   [Upload] Skipping RAG indexing for publication {new_pub.id} (insufficient text)")
        
        return {
            "id": new_pub.id,
            "status": "success",
            "filename": file.filename,
            "text_extracted": len(enriched_data["text"]) > 0,
            "doi_detected": enriched_data["doi_url"] is not None,
            "doi_url": enriched_data["doi_url"],
            "authors_matched": len(enriched_data["matched_author_ids"]),
            "author_names": author_names,
            "summaries_generated": bool(enriched_data["resumen_es"]),
            "processing_notes": enriched_data["processing_notes"],
            
            # ✅ NUEVO: Información de indexación RAG
            "rag_indexed": rag_result.get("success", False),
            "rag_chunks": rag_result.get("chunks_created", 0),
            "rag_searchable": rag_result.get("now_searchable", False),
            "rag_already_indexed": rag_result.get("already_indexed", False),
            
            "message": "PDF procesado y enriquecido exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")


@router.delete("/{pub_id}")
async def delete_publication(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Delete a publication and all its related data.
    Requires Editor role.
    """
    try:
        # Check if publication exists
        publication = db.query(Publication).filter(Publication.id == pub_id).first()
        
        if not publication:
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        
        # Delete related data using legacy DB connection for chunks
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete publication chunks (RAG data)
        cursor.execute("DELETE FROM publication_chunks WHERE publicacion_id = ?", (pub_id,))
        chunks_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Delete researcher-publication relationships (using SQLAlchemy)
        from core.models import ResearcherPublication
        db.query(ResearcherPublication).filter(
            ResearcherPublication.publicacion_id == pub_id
        ).delete()
        
        # Delete the publication itself
        db.delete(publication)
        db.commit()
        
        # Reload RAG embeddings if chunks were deleted
        if chunks_deleted > 0:
            try:
                from services.rag_service import get_semantic_engine
                engine = get_semantic_engine()
                engine._load_publication_embeddings()
                print(f"   [Delete] Reloaded RAG embeddings after deleting publication {pub_id}")
            except Exception as e:
                print(f"   [Warning] Failed to reload RAG embeddings: {e}")
        
        return {
            "status": "success",
            "message": f"Publicación {pub_id} eliminada exitosamente",
            "chunks_deleted": chunks_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error eliminando publicación: {str(e)}")


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
