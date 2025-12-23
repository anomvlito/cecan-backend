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


@router.post("/extract-missing-dois")
async def extract_missing_dois(
    dry_run: bool = False,
    force_recheck: bool = False,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Extract DOIs from publications.
    Args:
        dry_run: If True, don't save changes
        force_recheck: If True, scan ALL publications even if they have URL
        limit: Max publications to scan
    """
    from services.publication_service import extract_doi
    
    try:
        query = db.query(Publication)
        
        # If not forcing recheck, only get ones without canonical DOI
        if not force_recheck:
            query = query.filter(Publication.canonical_doi.is_(None))
            
        publications = query.limit(limit).all()
        
        total_scanned = len(publications)
        dois_found = 0
        dois_updated = 0
        failed = 0
        skipped = 0
        details = []
        
        print(f"[Extract DOIs] Processing {total_scanned} publications (dry_run={dry_run})")
        
        # Pre-load existing DOIs to check for duplicates and avoid IntegrityError
        # (This avoids crashing the batch if duplicates are found)
        existing_dois_rows = db.query(Publication.canonical_doi).filter(Publication.canonical_doi.isnot(None)).all()
        existing_dois = {row[0] for row in existing_dois_rows if row[0]}
        
        for pub in publications:
            try:
                # Debug: Check what we have
                has_text = bool(pub.contenido_texto and len(pub.contenido_texto) > 50)
                print(f"  [Pub {pub.id}] Title: {pub.titulo[:50]}... | Has text: {has_text} | Text length: {len(pub.contenido_texto) if pub.contenido_texto else 0}")
                
                # Skip if no text content
                if not pub.contenido_texto or len(pub.contenido_texto) < 50:
                    skipped += 1
                    details.append({
                        "pub_id": pub.id,
                        "title": pub.titulo[:50] if pub.titulo else "Sin título",
                        "status": "skipped",
                        "reason": "No text content"
                    })
                    continue
                
                # Try to extract DOI from text
                doi_url = extract_doi(pub.contenido_texto)
                
                if doi_url:
                    dois_found += 1
                    
                    # Extract clean DOI
                    from services.openalex_service import extract_doi_from_url
                    clean_doi = extract_doi_from_url(doi_url)
                    
                    # Check for duplicates (unless it's the same publication being re-scanned)
                    if clean_doi in existing_dois and pub.canonical_doi != clean_doi:
                        print(f"  ⚠️ Duplicate DOI found (ignoring update): {clean_doi}")
                        skipped += 1
                        details.append({
                            "pub_id": pub.id,
                            "title": pub.titulo[:50] if pub.titulo else "Sin título",
                            "status": "skipped_duplicate",
                            "doi": clean_doi,
                            "reason": "DOI already exists in another publication"
                        })
                        continue
                    
                    print(f"  ✓ Found DOI: {clean_doi}")
                    
                    if not dry_run:
                        # Update publication
                        pub.url_origen = doi_url
                        pub.canonical_doi = clean_doi
                        dois_updated += 1
                        existing_dois.add(clean_doi)
                    
                    details.append({
                        "pub_id": pub.id,
                        "title": pub.titulo[:50] if pub.titulo else "Sin título",
                        "status": "found" if dry_run else "updated",
                        "doi": clean_doi
                    })
                else:
                    # Show first 200 chars of text for debugging
                    text_preview = pub.contenido_texto[:200] if pub.contenido_texto else ""
                    print(f"  ✗ No DOI found. Text preview: {text_preview}...")
                    
                    details.append({
                        "pub_id": pub.id,
                        "title": pub.titulo[:50] if pub.titulo else "Sin título",
                        "status": "not_found",
                        "reason": "No DOI pattern detected"
                    })
            
            except Exception as e:
                failed += 1
                details.append({
                    "pub_id": pub.id,
                    "title": pub.titulo[:50] if pub.titulo else "Sin título",
                    "status": "error",
                    "error": str(e)
                })
                print(f"  ✗ Error processing {pub.id}: {str(e)}")
        
        # Commit changes if not dry run
        if not dry_run and dois_updated > 0:
            db.commit()
            print(f"[Extract DOIs] ✅ Updated {dois_updated} publications")
        
        print(f"[Extract DOIs] Summary: Scanned={total_scanned}, Found={dois_found}, Updated={dois_updated}, Skipped={skipped}, Failed={failed}")
        
        return {
            "status": "completed",
            "dry_run": dry_run,
            "scanned": total_scanned,
            "dois_found": dois_found,
            "dois_updated": dois_updated if not dry_run else 0,
            "skipped": skipped,
            "failed": failed,
            "details": details,
            "message": f"{'[DRY RUN] ' if dry_run else ''}Escaneadas {total_scanned} publicaciones, {dois_found} DOIs encontrados{', ' + str(dois_updated) + ' actualizados' if not dry_run else ''}"
        }
    
    except Exception as e:
        db.rollback()
        print(f"[Extract DOIs] ❌ Error: {str(e)}")
        return {
            "status": "error",
            "message": f"Error extrayendo DOIs: {str(e)}"
        }


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
        
        # ✅ Check for duplicates (Idempotency)
        # Use filename as a simple proxy for duplicate detection
        clean_title = file.filename.replace('.pdf', '').replace('_', ' ')
        
        existing_pub = db.query(Publication).filter(
            Publication.titulo == clean_title
        ).first()
        
        if existing_pub:
            # Publication already exists - return existing record instead of reprocessing
            print(f"   [Upload] Duplicate detected: '{clean_title}' already exists (ID: {existing_pub.id})")
            
            # Get existing authors
            from core.models import ResearcherPublication, AcademicMember
            existing_authors = db.query(AcademicMember).join(ResearcherPublication).filter(
                ResearcherPublication.publicacion_id == existing_pub.id
            ).all()
            author_names = [a.full_name for a in existing_authors]
            
            # Check if already indexed in RAG
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM publication_chunks WHERE publicacion_id = ?", (existing_pub.id,))
            existing_chunks = cursor.fetchone()[0]
            conn.close()
            
            return {
                "id": existing_pub.id,
                "status": "duplicate",
                "filename": file.filename,
                "text_extracted": bool(existing_pub.contenido_texto),
                "doi_detected": bool(existing_pub.url_origen),
                "doi_url": existing_pub.url_origen,
                "authors_matched": len(existing_authors),
                "author_names": author_names,
                "summaries_generated": bool(existing_pub.resumen_es),
                "processing_notes": [
                    "⚠️ Publicación duplicada detectada",
                    f"Ya existe con ID {existing_pub.id}",
                    "No se procesó nuevamente para ahorrar cuota de API"
                ],
                "rag_indexed": existing_chunks > 0,
                "rag_chunks": existing_chunks,
                "rag_searchable": existing_chunks > 0,
                "rag_already_indexed": True,
                "message": f"Publicación duplicada: ya existe como ID {existing_pub.id}"
            }
        
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


from pydantic import BaseModel

class PublicationUpdate(BaseModel):
    canonical_doi: str | None = None

@router.patch("/{pub_id}")
async def update_publication(
    pub_id: int,
    update_data: PublicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Update publication details (currently only DOI).
    Requires Editor role.
    """
    pub = db.query(Publication).filter(Publication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    
    if update_data.canonical_doi is not None:
        # Clean DOI if necessary (remove https://doi.org/ prefix)
        clean_doi = update_data.canonical_doi.strip()
        if "doi.org/" in clean_doi:
            clean_doi = clean_doi.split("doi.org/")[-1]
            
        pub.canonical_doi = clean_doi
        # Also update origin URL if it was empty or autogenerated
        if not pub.url_origen or "doi.org" in pub.url_origen:
             pub.url_origen = f"https://doi.org/{clean_doi}"
             
    db.commit()
    db.refresh(pub)
    return pub

@router.post("/{pub_id}/enrich-openalex")
async def enrich_publication_with_openalex(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Enrich a publication with metrics from OpenAlex using its DOI.
    Requires Editor role.
    
    Updates:
    - PublicationImpact with citation count and collaboration status
    - Publication.canonical_doi with normalized DOI
    
    Returns enriched metrics and OpenAlex data.
    """
    from services.openalex_service import (
        get_publication_by_doi,
        extract_doi_from_url,
        detect_international_collab,
        extract_journal_info,
        get_openalex_id
    )
    from core.models import PublicationImpact
    
    try:
        # 1. Get publication from database
        publication = db.query(Publication).filter(Publication.id == pub_id).first()
        
        if not publication:
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        
        # 2. Validate that publication has DOI
        if not publication.url_origen:
            raise HTTPException(
                status_code=400,
                detail="Publicación no tiene DOI. No se puede enriquecer con OpenAlex."
            )
        
        # 3. Extract clean DOI
        clean_doi = extract_doi_from_url(publication.url_origen)
        print(f"[Enrich] Processing publication {pub_id} with DOI: {clean_doi}")
        
        # 4. Query OpenAlex API
        openalex_data = get_publication_by_doi(clean_doi)
        
        # 5. Extract metrics
        citation_count = openalex_data.get("cited_by_count", 0)
        is_international = detect_international_collab(openalex_data)
        journal_info = extract_journal_info(openalex_data)
        openalex_id = get_openalex_id(openalex_data)
        
        # 6. Update or create PublicationImpact
        impact = db.query(PublicationImpact).filter(
            PublicationImpact.publication_id == pub_id
        ).first()
        
        if not impact:
            impact = PublicationImpact(publication_id=pub_id)
            db.add(impact)
            print(f"[Enrich] Creating new PublicationImpact for pub {pub_id}")
        else:
            print(f"[Enrich] Updating existing PublicationImpact for pub {pub_id}")
        
        # Update metrics
        impact.citation_count = citation_count
        impact.is_international_collab = is_international
        
        # 7. Update publication canonical_doi
        publication.canonical_doi = clean_doi
        
        # 8. Commit changes
        db.commit()
        db.refresh(impact)
        
        print(f"[Enrich] ✅ Successfully enriched publication {pub_id}")
        print(f"         Citations: {citation_count}, International: {is_international}")
        
        return {
            "status": "success",
            "publication_id": pub_id,
            "doi": clean_doi,
            "openalex_id": openalex_id,
            "metrics": {
                "citations": citation_count,
                "is_international_collab": is_international
            },
            "journal": journal_info,
            "message": f"Publicación enriquecida con {citation_count} citas desde OpenAlex"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Enrich] ❌ Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error enriqueciendo publicación: {str(e)}"
        )
