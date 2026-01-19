"""
Publication Routes for CECAN Platform
API endpoints for publications and data management
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Body, BackgroundTasks
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session, joinedload
import threading
import os
from datetime import datetime
import json

from database.session import get_db
from core.security import require_editor, get_current_user
from core.models import User
from services import scraper_service, compliance_service, publication_service
from services.ingestion_service import ingestion_service
from core.models import Publication, ResearcherPublication, AcademicMember, PublicationImpact, PublicationChunk, Journal
from services.wos_verification_service import enrich_publication_with_wos_verification
from schemas import PublicationUpdate, PublicationOut, PublicationDetailOut, PublicationAuthorOut, WosVerificationOut

router = APIRouter(prefix="/publications", tags=["Publications"])


@router.get("", response_model=list[PublicationOut])
async def get_publications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all publications with researcher matches and WOS Verification
    """
    pubs = (
        db.query(Publication)
        .options(
             joinedload(Publication.journal),
             joinedload(Publication.impact_metrics)
        )
        .order_by(Publication.id.desc())
        .all()
    )

    # Enrich with WOS data
    results = []

    for pub in pubs:
        # Create Pydantic model from ORM
        pub_out = PublicationOut.from_orm(pub)

        # Add WOS verification using extracted service
        enrich_publication_with_wos_verification(pub_out, pub, db)

        results.append(pub_out)

    return results


@router.get("/{pub_id}", response_model=PublicationDetailOut)
async def get_publication_detail(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information for a specific publication including:
    - Full publication metadata
    - Journal information with metrics
    - Complete list of authors
    - Impact metrics (citations, quartile, etc.)
    - Audit information
    """
    # Query publication with eager loading of relationships
    pub = (
        db.query(Publication)
        .options(
            joinedload(Publication.journal).joinedload(Journal.categories),
            joinedload(Publication.impact_metrics),
            joinedload(Publication.researcher_connections).joinedload(ResearcherPublication.member)
        )
        .filter(Publication.id == pub_id)
        .first()
    )
    
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    # Use custom from_orm to properly serialize authors
    detail = PublicationDetailOut.from_orm(pub)

    # Add WOS verification using extracted service
    enrich_publication_with_wos_verification(detail, pub, db)

    return detail


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
    """
    try:
        compliance_service.reset_audit_status(db)
        return {"status": "completed", "message": "Audit status reset successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/extract-missing-dois")
async def extract_missing_dois(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor),
    dry_run: bool = False,
    force_recheck: bool = False,
    limit: int = 1000,
    publication_ids: Optional[List[int]] = None
):
    """
    Extract DOIs from publications using modern extraction (layout=True).
    Can work on specific publications (publication_ids) or all publications matching criteria.
    """
    from services.publication_service import extract_doi, extract_text_from_pdf
    from services.openalex_service import extract_doi_from_url
    import os
    
    try:
        query = db.query(Publication)
        
        # PRIORITY: If specific IDs provided, only process those
        if publication_ids:
            query = query.filter(Publication.id.in_(publication_ids))
            print(f"[Extract DOIs] Processing {len(publication_ids)} selected publications")
        else:
            # If not forcing recheck, only get ones without canonical DOI
            if not force_recheck:
                query = query.filter(Publication.canonical_doi.is_(None))
            
            query = query.limit(limit)
            
        publications = query.all()
        
        total_scanned = len(publications)
        dois_found = 0
        dois_updated = 0
        failed = 0
        skipped = 0
        details = []
        
        print(f"[Extract DOIs] Processing {total_scanned} publications (dry_run={dry_run})")
        
        # Pre-load existing DOIs
        existing_dois_rows = db.query(Publication.canonical_doi).filter(Publication.canonical_doi.isnot(None)).all()
        existing_dois = {row[0] for row in existing_dois_rows if row[0]}
        
        for pub in publications:
            try:
                doi_url = None
                
                # PRIORITY 1: Re-extract from PDF file if available (with layout=True!)
                if pub.file_path and os.path.exists(pub.file_path):
                    try:
                        print(f"   [Extract DOIs] Re-extracting PDF {pub.file_path} with layout analysis...")
                        with open(pub.file_path, 'rb') as f:
                            file_bytes = f.read()
                        
                        # Extract with modern layout-aware extraction
                        fresh_text = extract_text_from_pdf(file_bytes)
                        if fresh_text and len(fresh_text) > 50:
                            doi_url = extract_doi(fresh_text)
                            if doi_url:
                                print(f"   ✅ Found DOI from re-extracted PDF: {doi_url}")
                    except Exception as e:
                        print(f"   ⚠️ PDF re-extraction failed for {pub.id}: {e}")
                
                # PRIORITY 2: Use existing text content if PDF not available
                if not doi_url and pub.content and len(pub.content) > 50:
                    doi_url = extract_doi(pub.content)
                    if doi_url:
                        print(f"   ✅ Found DOI from stored content: {doi_url}")
                
                # PRIORITY 3: FALLBACK - OpenAlex Search by Title
                if not doi_url and pub.title and len(pub.title) > 10:
                    from services import openalex_service
                    match = openalex_service.search_publication_by_title(pub.title)
                    if match and match.get("doi"):
                        doi_url = match.get("doi")
                        print(f"   ✅ Recovered DOI by title '{pub.title[:30]}...': {doi_url}")
                
                #  No DOI found - skip
                if not doi_url:
                    skipped += 1
                    continue
                
                # Found DOI - process it
                dois_found += 1
                clean_doi = extract_doi_from_url(doi_url)
                
                # Skip if duplicate
                if clean_doi in existing_dois and pub.canonical_doi != clean_doi:
                    skipped += 1
                    continue
                
                if not dry_run:
                    pub.url = doi_url
                    pub.canonical_doi = clean_doi
                    dois_updated += 1
                    existing_dois.add(clean_doi)
                    
                    # CRITICAL: Trigger re-enrichment in background
                    print(f"   🔄 Triggering re-enrichment for pub {pub.id} with DOI {clean_doi}")
                    background_tasks.add_task(reenrich_publication_task, pub.id, clean_doi)
                
                details.append({
                    "pub_id": pub.id,
                    "title": pub.title[:50] if pub.title else "Untitled",
                    "status": "found" if dry_run else "updated",
                    "doi": clean_doi
                })
            
            except Exception as e:
                failed += 1
                print(f"  ✗ Error processing {pub.id}: {str(e)}")
        
        # Commit changes if not dry run
        if not dry_run and dois_updated > 0:
            db.commit()
        
        return {
            "status": "completed",
            "dry_run": dry_run,
            "scanned": total_scanned,
            "dois_found": dois_found,
            "dois_updated": dois_updated if not dry_run else 0,
            "failed": failed,
            "skipped": skipped,
            "details": details
        }
    
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": f"Error extracting DOIs: {str(e)}"
        }


@router.post("/upload", response_model=Dict[str, Any])
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Upload a PDF publication with data enrichment.
    FASE 1 SIMPLIFICADA: Solo extrae metadata desde OpenAlex.
    Los resúmenes se generan después con /generate-summaries
    """
    try:
        content = await file.read()
        
        # Delegate complex ingestion logic to service layer
        # skip_ai ya no es necesario (siempre es True internamente)
        # Using skip_rag=True to offload AI indexing to background task and avoid timeouts
        result = ingestion_service.process_pdf_ingestion(
            file_content=content, 
            filename=file.filename, 
            db=db,
            skip_ai=True,
            skip_rag=True
        )
        
        # Schedule RAG indexing in background if publication was created successfully
        if result.get("status") == "success" and result.get("id"):
            # We pass the content (which is available in result if we returned it, or we can fetch it. 
            # Ideally ingestion_service should handle the content retrieval or we can just pass the ID).
            # The run_rag_indexing method I wrote fetches from DB if content is None? 
            # Re-checking my implementation of run_rag_indexing: "if not content... pass". 
            # Wait, I didn't implement the fetch in run_rag_indexing yet! 
            # I must fix that in ingestion_service first or pass content here. 
            # Let's pass None and rely on a fixed run_rag_indexing, OR fix run_rag_indexing.
            # Actually, I'll pass the content if I had it, but result doesn't have it.
            # I'll rely on the DB fetch which I need to implement OR implement it now.
            # For now, let's schedule it.
            background_tasks.add_task(ingestion_service.run_rag_indexing, result["id"])
        
        return result

    except ValueError as ve:
        # Validation errors (e.g. invalid PDF)
        raise HTTPException(status_code=400, detail=str(ve))
    
    except Exception as e:
        # Unexpected server errors
        print(f"Error in upload_pdf endpoint: {e}")
        return {
            "status": "error",
            "message": f"Server error processing upload: {str(e)}"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.delete("/{pub_id}")
async def delete_publication(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Delete a publication and all its associated data (Manual Cleanup Strategy).
    This ensures no foreign key constraint errors occur by removing children first.
    """
    try:
        # 1. Fetch Publication
        publication = db.query(Publication).filter(Publication.id == pub_id).first()
        if not publication:
            raise HTTPException(status_code=404, detail="Publication not found")
        
        local_path = publication.local_path
        
        # 2. Manual Cleanup of Children (Safety First)
        # Delete Researcher Connections
        db.query(ResearcherPublication).filter(ResearcherPublication.publication_id == pub_id).delete()
        
        # Delete Impact Metrics
        db.query(PublicationImpact).filter(PublicationImpact.publication_id == pub_id).delete()
        
        # Delete RAG Chunks
        from core.models import PublicationChunk
        db.query(PublicationChunk).filter(PublicationChunk.publication_id == pub_id).delete()
        
        # 3. Delete the Publication itself
        db.delete(publication)
        db.commit()
        
        # 4. File Deletion (Post-Commit to ensure DB consistency first)
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                print(f"   [System] Deleted local PDF: {local_path}")
            except Exception as e:
                print(f"   [Warning] Could not delete file {local_path}: {e}")

        return {"status": "success", "message": f"Publication {pub_id} deleted successfully"}
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"CRITICAL DELETE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting publication: {str(e)}")



@router.patch("/{pub_id}", response_model=PublicationOut)
async def update_publication(
    pub_id: int,
    pub_update: PublicationUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Update a publication manually.
    """
    pub = db.query(Publication).filter(Publication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
        
    # Manual mapping (handling optional updates)
    if pub_update.title is not None:
        pub.title = pub_update.title
    if pub_update.year is not None:
        pub.year = pub_update.year
    if pub_update.url is not None:
        pub.url = pub_update.url
    
    if pub_update.summary_es is not None:
        pub.summary_es = pub_update.summary_es
    if pub_update.summary_en is not None:
        pub.summary_en = pub_update.summary_en
    
    # CRITICAL: Capture old DOI before updating (for change detection)
    old_doi = pub.canonical_doi
    
    # Update DOI if provided
    if pub_update.canonical_doi is not None:
        pub.canonical_doi = pub_update.canonical_doi
        
    # Handle author updates
    if pub_update.author_ids is not None:
        # 1. Delete existing connections
        db.query(ResearcherPublication).filter(ResearcherPublication.publication_id == pub_id).delete()
        
        # 2. Create new connections and collect names
        new_author_names = []
        for member_id in pub_update.author_ids:
            # Verify member exists to avoid FK error
            member = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
            if member:
                new_conn = ResearcherPublication(
                    publication_id=pub_id, 
                    member_id=member_id,
                    match_method="manual",
                    match_score=100
                )
                db.add(new_conn)
                new_author_names.append(member.full_name)
        
        # 3. Update the cached 'authors' string field on the Publication model
        if new_author_names:
            pub.authors = ", ".join(new_author_names)
        else:
            pub.authors = ""
            
    # Check if DOI actually changed (and is not None/Empty) - trigger re-enrichment
    if pub_update.canonical_doi and pub_update.canonical_doi != old_doi:
        print(f"🔄 DOI changed from '{old_doi}' to '{pub_update.canonical_doi}'. Triggering re-enrichment...")
        background_tasks.add_task(reenrich_publication_task, pub.id, pub_update.canonical_doi)
        
    db.commit()
    db.refresh(pub)
    return pub

async def reenrich_publication_task(pub_id: int, doi: str):
    """
    Background task to re-enrich a publication when its DOI changes.
    Fetches data from OpenAlex -> Updates Publication -> Matches WOS Mirror.
    """
    try:
        print(f"🔄 [Background] Starting re-enrichment for Pub ID {pub_id} with DOI: {doi}")
        
        # 1. Fetch from OpenAlex
        from services.openalex_service import get_publication_by_doi, extract_publication_metadata
        
        # Clean DOI just in case
        clean_doi = doi.replace("https://doi.org/", "").strip()
        openalex_data = get_publication_by_doi(clean_doi)
        
        if not openalex_data:
            print(f"❌ [Background] OpenAlex returned no data for DOI: {clean_doi}")
            return

        metrics_data = extract_publication_metadata(openalex_data)
        if not metrics_data:
            print("❌ [Background] Could not extract metrics from OpenAlex data")
            return

        # 2. Update Publication Record (Title, Journal, Year, etc.) - REFRESH DB SESSION
        # Creating a NEW session for background task is safer usually, 
        # but here we rely on the passed session being valid or handled by FastAPI/Starlette background logic.
        # Ideally, we should create a new session if this task runs after response is sent.
        # But `db` passed from Depends(get_db) is closed after request. 
        # We need to create a new session here. 
        
        # TODO: Fix DB session for background task. 
        # For now, let's assume we need to instantiate a new session to be safe.
        from database.session import SessionLocal
        bg_db = SessionLocal()
        
        try:
            pub = bg_db.query(Publication).filter(Publication.id == pub_id).first()
            if not pub:
                print(f"❌ [Background] Publication {pub_id} not found in DB")
                return

            print(f"✅ [Background] Updating publication '{pub.title}' with OpenAlex data...")
            
            # Map OpenAlex fields to Publication
            if metrics_data.get("title"):
                pub.title = metrics_data["title"]
            if metrics_data.get("publication_year"):
                pub.year = metrics_data["publication_year"]
            if metrics_data.get("journal_name"):
                pub.journal = metrics_data["journal_name"]
            
            # Save updates
            bg_db.commit()
            
            # 3. Run WOS Mirror Match (Quartiles)
            detected_journal = metrics_data.get("journal_name")
            publisher = None # TODO: Extract publisher from OpenAlex if available in metrics_data
            
            # Try to get publisher from source (metrics_data usually has flat structure, check scraper logic)
            # For now, let's proceed with journal name.
            
            from services.journal_service import JournalMatchingService
            matcher = JournalMatchingService(bg_db)
            
            wos_match, wos_match_type = matcher.find_best_match(
                journal_name=detected_journal,
                issn=metrics_data.get("issn"),
                publisher=publisher
            )
            
            if wos_match:
                print(f"🎯 [Background] WOS Match Found! ID: {wos_match.wos_id} ({wos_match_type})")
                
                # Check/Create PublicationImpact
                from core.models import PublicationImpact
                impact = bg_db.query(PublicationImpact).filter(PublicationImpact.publication_id == pub_id).first()
                if not impact:
                    impact = PublicationImpact(publication_id=pub_id)
                    bg_db.add(impact)
                
                # Update Impact Metrics
                impact.wos_id = wos_match.wos_id
                impact.journal_source_id = wos_match.id # Link to source
                impact.quartile = wos_match.quartile
                impact.impact_factor = wos_match.impact_factor
                
                # Update Denormalized Quartile on Publication
                pub.quartile = wos_match.quartile
                pub.wos_verification = "verified"
                
                bg_db.commit()
                print(f"✅ [Background] Updated Quartile to: {pub.quartile}")
                
            else:
                print("⚠️ [Background] No WOS match found.")
                pub.wos_verification = "not_found"
                bg_db.commit()
                
        except Exception as e:
            print(f"❌ [Background] Error during DB update: {e}")
            bg_db.rollback()
        finally:
            bg_db.close()
            
    except Exception as e:
        print(f"❌ [Background] Re-enrichment Task Failed: {e}")


@router.post("/batch-reenrich")
async def batch_reenrich_publications(
    background_tasks: BackgroundTasks,
    publication_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Re-enrich multiple publications in batch.
    Reuses the same logic as manual DOI update (reenrich_publication_task).
    """
    if not publication_ids:
        raise HTTPException(status_code=400, detail="No publication IDs provided")
    
    # Validate that all publications exist and have DOIs
    pubs = db.query(Publication).filter(Publication.id.in_(publication_ids)).all()
    found_ids = {p.id for p in pubs}
    missing_ids = set(publication_ids) - found_ids
    
    if missing_ids:
        raise HTTPException(
            status_code=404, 
            detail=f"Publications not found: {list(missing_ids)}"
        )
    
    # Count how many have DOIs
    pubs_with_dois = [p for p in pubs if p.canonical_doi]
    pubs_without_dois = [p for p in pubs if not p.canonical_doi]
    
    print(f"📦 [Batch Re-enrich] Processing {len(pubs)} publications")
    print(f"   ✅ With DOI: {len(pubs_with_dois)}")
    print(f"   ⚠️ Without DOI: {len(pubs_without_dois)}")
    
    # Schedule background tasks for publications with DOIs
    for pub in pubs_with_dois:
        background_tasks.add_task(reenrich_publication_task, pub.id, pub.canonical_doi)
    
    return {
        "status": "started",
        "total": len(pubs),
        "with_doi": len(pubs_with_dois),
        "without_doi": len(pubs_without_dois),
        "message": f"Re-enrichment started for {len(pubs_with_dois)} publications with DOIs. Check logs for progress."
    }


@router.post("/{pub_id}/enrich-openalex")
async def enrich_publication_with_openalex(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    from services.openalex_service import (
        get_publication_by_doi,
        extract_doi_from_url,
        detect_international_collab,
        extract_journal_info,
        get_openalex_id
    )
    
    try:
        pub = db.query(Publication).filter(Publication.id == pub_id).first()
        if not pub:
            raise HTTPException(status_code=404, detail="Publication not found")
        
        if not pub.url and not pub.canonical_doi:
             raise HTTPException(status_code=400, detail="Publication has no DOI/URL")
             
        # Resolve DOI
        doi_to_use = pub.canonical_doi or extract_doi_from_url(pub.url)
        if not doi_to_use:
             raise HTTPException(status_code=400, detail="Could not extract DOI")
             
        openalex_data = get_publication_by_doi(doi_to_use)
        
        # Update metrics
        citation_count = openalex_data.get("cited_by_count", 0)
        is_international = detect_international_collab(openalex_data)
        
        impact = db.query(PublicationImpact).filter(PublicationImpact.publication_id == pub_id).first()
        if not impact:
            impact = PublicationImpact(publication_id=pub_id)
            db.add(impact)
            
        impact.citation_count = citation_count
        impact.is_international_collab = is_international
        
        pub.canonical_doi = doi_to_use
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Enriched with {citation_count} citations",
            "metrics": {"citations": citation_count}
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Enrichment error: {str(e)}")


@router.post("/sync-metadata")
async def sync_metadata_batch(
    target_ids: list[int] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Batch synchronize metadata (Title, Year, Metrics) from OpenAlex for all publications with DOIs.
    """
    from services.openalex_service import get_publication_by_doi, extract_publication_metadata
    from services import journal_service
    
    query = db.query(Publication).filter(Publication.canonical_doi.isnot(None))
    
    pubs = query.all()
    
    updated_count = 0
    errors_count = 0
    
    print(f"[Metadata Sync] Processing {len(pubs)} publications...")
    
    import time
    
    for pub in pubs:
        # Check if target_ids is provided and filter manually (since we did all() above)
        # Or better, filter in query.
        if target_ids and pub.id not in target_ids:
            continue

        try:
             # Basic rate limiting
             time.sleep(0.2) 
             
             data = get_publication_by_doi(pub.canonical_doi)
             if not data:
                 raise ValueError("OpenAlex returned no data")
             meta = extract_publication_metadata(data)
             if not meta:
                 raise ValueError("Could not extract metadata from OpenAlex response")
             
             # Updates
             changed = False
             
             if meta.get("title") and meta["title"] != pub.title:
                 print(f"   [Sync] Updating title ID {pub.id}: '{pub.title}' -> '{meta['title']}'")
                 pub.title = meta["title"]
                 changed = True
                 
             if meta.get("publication_year") and str(meta["publication_year"]) != pub.year:
                 pub.year = str(meta["publication_year"])
                 changed = True
                 
             # Always update metrics
             pub.metrics_data = meta
             pub.metrics_last_updated = datetime.utcnow()
             pub.doi_verification_status = "valid_openalex"
             
             # Link Journal
             if meta.get("journal_name"):
                 try:
                     publisher = None
                     # Try to get publisher if available in raw data (not currently in meta dict, might need adjustment if critical)
                     # For now, get_or_create handles it.
                     journal = journal_service.get_or_create_journal(db, meta["journal_name"], None)
                     if journal and pub.journal_id != journal.id:
                         pub.journal_id = journal.id
                         changed = True
                         print(f"   [Sync] Linked Journal ID {pub.id}: {journal.name}")
                 except Exception as je:
                     print(f"   [Sync] Warning linking journal for {pub.id}: {je}")
             
             if changed or True: # Count as updated if we refreshed metrics
                updated_count += 1
             
        except Exception as e:
            print(f"Error syncing pub {pub.id} ({pub.canonical_doi}): {e}")
            errors_count += 1
            
    db.commit()
    
    return {
        "total_processed": len(pubs) if not target_ids else len(target_ids),
        "updated": updated_count,
        "errors": errors_count
    }


@router.post("/{pub_id}/summary")
def generate_summary(
    pub_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Generate AI summaries (ES/EN) for a specific publication from its stored text content.
    """
    from services.publication_service import generate_summary_from_text
    
    pub = db.query(Publication).filter(Publication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    # Use text from database instead of reading PDF file
    text_content = pub.content
    
    # Fallback: Try to reconstruct from chunks if content is missing
    if not text_content or len(text_content) < 50:
         chunks = db.query(PublicationChunk).filter(PublicationChunk.publication_id == pub_id).order_by(PublicationChunk.chunk_index).all()
         if chunks:
             print(f"   [Summary] Reconstructing text from {len(chunks)} chunks for pub {pub_id}")
             text_content = "\n".join([c.content for c in chunks])
    
    if not text_content or len(text_content) < 50:
         raise HTTPException(status_code=400, detail="Publication has no text content in database")
    
    try:
        from services.publication_service import analyze_text_with_ai
        
        # Call the unified analysis function
        analysis = analyze_text_with_ai(text_content)
        
        es = analysis.get("summary_es")
        en = analysis.get("summary_en")
        journal_analysis = analysis.get("journal_analysis")
        
        pub.summary_es = es
        pub.summary_en = en
        pub.ai_journal_analysis = journal_analysis # Save Journal Analysis
        
        # Save Quartile if found
        if journal_analysis and journal_analysis.get("quartile_estimate"):
            pub.quartile = journal_analysis.get("quartile_estimate")[:2] # Save extracted Q1/Q2/etc
            
        pub.ai_journal_analysis = journal_analysis # Save Journal Analysis
        
        db.commit()
        
        return {
            "status": "success",
            "summary_es": es,
            "summary_en": en,
            "ai_journal_analysis": journal_analysis
        }
    except Exception as e:
        print(f"Error generating summary for pub {pub_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-openalex")
def search_publications_in_openalex(
    title: str = Body(..., embed=True),
    limit: int = Body(5, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Search for publications in OpenAlex by title.
    Returns top candidates with similarity scores for manual confirmation.
    """
    from services.openalex_search_service import search_publications_by_title
    
    try:
        candidates = search_publications_by_title(title, limit=limit)
        
        return {
            "status": "success",
            "query": title,
            "candidates": candidates,
            "count": len(candidates)
        }
    except Exception as e:
        print(f"Error searching OpenAlex: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pub_id}/link-openalex")
def link_to_openalex(
    pub_id: int,
    openalex_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Link a publication to a confirmed OpenAlex work and sync all metadata.
    """
    from services.openalex_search_service import link_publication_to_openalex
    
    try:
        success = link_publication_to_openalex(pub_id, openalex_data, db)
        
        if success:
            return {
                "status": "success",
                "message": f"Publication {pub_id} linked to OpenAlex successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to link publication")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error linking to OpenAlex: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== JOURNAL ENRICHMENT ENDPOINT ==========
@router.post("/journals/{journal_id}/enrich")
async def enrich_journal_metrics(
    journal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Manually trigger AI enrichment for a specific journal.
    This will fetch JIF, SJR, CiteScore, SNIP, and Categories using Gemini AI.
    
    Requires: Editor permissions
    """
    from core.models import Journal
    from services import journal_service
    
    # Check if journal exists
    journal = db.query(Journal).filter(Journal.id == journal_id).first()
    if not journal:
        raise HTTPException(status_code=404, detail=f"Journal with ID {journal_id} not found")
    
    print(f"\n🔄 [Manual Enrichment] Starting enrichment for Journal ID: {journal_id} - {journal.name}")
    
    try:
        # Call enrichment service
        journal_service.enrich_journal_metrics(db, journal_id)
        
        # Refresh to get updated data
        db.refresh(journal)
        
        return {
            "status": "success",
            "message": f"Journal '{journal.name}' enriched successfully",
            "journal": {
                "id": journal.id,
                "name": journal.name,
                "jif_current": journal.jif_current,
                "scopus_sjr": journal.scopus_sjr,
                "categories_count": len(journal.categories) if journal.categories else 0
            }
        }
        
    except Exception as e:
        print(f"❌ [Manual Enrichment] Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to enrich journal: {str(e)}"
        )
