"""
Publication Routes for CECAN Platform
API endpoints for publications and data management
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Body
from sqlalchemy.orm import Session, joinedload
import threading
import os
from datetime import datetime
import json

from database.session import get_db
from core.security import require_editor, get_current_user
from core.models import User
from services import scraper_service, compliance_service, publication_service
from core.models import Publication, ResearcherPublication, AcademicMember, PublicationImpact
from schemas import PublicationUpdate, PublicationOut

router = APIRouter(prefix="/publications", tags=["Publications"])


@router.get("", response_model=list[PublicationOut])
async def get_publications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all publications with researcher matches
    """
    # Use SQLAlchemy to fetch publications with relationships if needed
    # For now, fetching basic data. 
    # Note: PublicationOut schema handles deserialization if configured correctly, 
    # but let's manualy check the metrics_data usage if it's stored as JSON-in-string or native JSON type in Postgres.
    # In Postgres `JSON` type comes out as dict, so no need for manual deserialization unless it was stored as string.
    
    pubs = db.query(Publication).order_by(Publication.id.desc()).all()
    # The Pydantic model `PublicationOut` should automatically handle the conversion 
    # from the ORM model to the JSON response.
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
    dry_run: bool = False,
    force_recheck: bool = False,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Extract DOIs from publications.
    """
    from services.publication_service import extract_doi
    from services.openalex_service import extract_doi_from_url
    
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
        
        # Pre-load existing DOIs
        existing_dois_rows = db.query(Publication.canonical_doi).filter(Publication.canonical_doi.isnot(None)).all()
        existing_dois = {row[0] for row in existing_dois_rows if row[0]}
        
        for pub in publications:
            try:
                # Use 'content' field instead of 'contenido_texto'
                has_text = bool(pub.content and len(pub.content) > 50)
                
                # Skip if no text content
                if not pub.content or len(pub.content) < 50:
                    skipped += 1
                    continue
                
                # Try to extract DOI from text
                doi_url = extract_doi(pub.content)
                
                if doi_url:
                    dois_found += 1
                    clean_doi = extract_doi_from_url(doi_url)
                    
                    if clean_doi in existing_dois and pub.canonical_doi != clean_doi:
                        skipped += 1
                        continue
                    
                    if not dry_run:
                        pub.url = doi_url # Renamed from url_origen
                        pub.canonical_doi = clean_doi
                        dois_updated += 1
                        existing_dois.add(clean_doi)
                    
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
            "details": details
        }
    
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": f"Error extracting DOIs: {str(e)}"
        }


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    skip_ai: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Upload a PDF publication with data enrichment.
    """
    try:
        content = await file.read()
        
        # Validate PDF
        is_valid, error_msg = publication_service.validate_pdf_file(file.filename, content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        clean_title = file.filename.replace('.pdf', '').replace('_', ' ')
        
        # Check duplicate by title
        existing_pub = db.query(Publication).filter(
            Publication.title == clean_title # Renamed from titulo
        ).first()
        
        if existing_pub:
            return {
                "id": existing_pub.id,
                "status": "duplicate",
                "message": f"Publication duplicate: ID {existing_pub.id}"
            }
        
        # Enrich data
        enriched_data = publication_service.enrich_publication_data(content, file.filename, db, skip_ai=skip_ai)
        
        # Save PDF file to disk
        pdf_directory = "data/publications"
        os.makedirs(pdf_directory, exist_ok=True)
        safe_filename = file.filename.replace(' ', '_').replace('/', '_')
        file_path = os.path.join(pdf_directory, safe_filename)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        print(f"   [System] Saved PDF to: {file_path}")
        
        # Determine authors string
        author_names = []
        if enriched_data["matched_author_ids"]:
            authors = db.query(AcademicMember).filter(
                AcademicMember.id.in_(enriched_data["matched_author_ids"])
            ).all()
            author_names = [a.full_name for a in authors]
        
        autores_str = ", ".join(author_names) if author_names else "Unknown Authors"
        
        # Smart Year Detection + Metrics from OpenAlex (graceful degradation)
        publication_year = str(datetime.now().year)  # Fallback
        openalex_metrics = None
        canonical_doi_value = enriched_data.get("doi")
        doi_status = "pending"
        
        if canonical_doi_value:
            try:
                from services.openalex_service import get_publication_by_doi, extract_publication_metadata
                print(f"   [OpenAlex] Fetching metadata for DOI: {canonical_doi_value}")
                openalex_data = get_publication_by_doi(canonical_doi_value)
                openalex_metrics = extract_publication_metadata(openalex_data)
                doi_status = "valid_openalex"
                
                # Extract year and title from OpenAlex
                if openalex_metrics:
                    if openalex_metrics.get("publication_year"):
                        publication_year = str(openalex_metrics["publication_year"])
                        print(f"   [OpenAlex] ✅ Year detected: {publication_year}")
                    
                    if openalex_metrics.get("title"):
                        clean_title = openalex_metrics["title"]
                        print(f"   [OpenAlex] ✅ Title detected: {clean_title}")

            except Exception as e:
                print(f"   [OpenAlex] ⚠️  Could not fetch metadata: {e}")
                # Continue with defaults - don't crash upload
        
        # Extract ORCIDs from PDF hyperlinks
        orcids_list = []
        author_metadata = None
        try:
            from services.orcid_metadata_service import (
                extract_orcids_from_pdf_hyperlinks,
                enrich_orcids_with_metadata
            )
            
            orcids_list = extract_orcids_from_pdf_hyperlinks(content)
            if orcids_list:
                print(f"   [ORCID] Found {len(orcids_list)} ORCIDs in PDF hyperlinks")
                author_metadata = enrich_orcids_with_metadata(orcids_list)
        except Exception as orcid_error:
            print(f"   [ORCID] Warning: Could not extract ORCID metadata: {orcid_error}")
        
        # Create Publication
        new_pub = Publication(
            title=clean_title,
            authors=autores_str,
            year=publication_year,
            url=enriched_data.get("doi_url"),
            local_path=file_path,  # Add saved file path
            content=enriched_data.get("text", ""),
            summary_es=enriched_data.get("resumen_es"),
            summary_en=enriched_data.get("resumen_en"),
            canonical_doi=canonical_doi_value,
            doi_verification_status=doi_status,
            extracted_orcids=",".join(orcids_list) if orcids_list else None,  # Store ORCIDs
            author_metadata=author_metadata,  # Store author countries and names
            ai_journal_analysis=enriched_data.get("ai_journal_analysis"), # Store AI journal analysis
            quartile=enriched_data.get("ai_journal_analysis", {}).get("quartile_estimate")[:2] if enriched_data.get("ai_journal_analysis") and enriched_data.get("ai_journal_analysis").get("quartile_estimate") else None, # Store Quartile
            metrics_data=openalex_metrics if openalex_metrics else None,
            metrics_last_updated=datetime.utcnow() if openalex_metrics else None,
            has_funding_ack=False,
            anid_report_status="Pending"
        )
        
        db.add(new_pub)
        db.commit()
        db.refresh(new_pub)
        
        # Create relations
        for author_id in enriched_data["matched_author_ids"]:
            connection = ResearcherPublication(
                member_id=author_id,
                publication_id=new_pub.id, # Renamed
                match_score=100,
                match_method="text_match"
            )
            db.add(connection)
        
        db.commit()
        
        # RAG Indexing
        from services.rag_service import get_semantic_engine
        rag_result = {"success": False}
        if new_pub.content and len(new_pub.content) > 100:
            try:
                engine = get_semantic_engine()
                rag_result = engine.process_single_publication(new_pub.id)
            except Exception as e:
                print(f"RAG Indexing failed: {e}")

        return {
            "id": new_pub.id,
            "status": "success",
            "message": "PDF uploaded and enriched successfully",
            "rag_indexed": rag_result.get("success", False)
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
    if pub_update.canonical_doi is not None:
        pub.canonical_doi = pub_update.canonical_doi
    
    if pub_update.summary_es is not None:
        pub.summary_es = pub_update.summary_es
    if pub_update.summary_en is not None:
        pub.summary_en = pub_update.summary_en
    if pub_update.quartile is not None:
        pub.quartile = pub_update.quartile
        
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
        
    db.commit()
    db.refresh(pub)
    return pub


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
    if not pub.content or len(pub.content) < 50:
         raise HTTPException(status_code=400, detail="Publication has no text content in database")
         
    try:
        from services.publication_service import analyze_text_with_ai
        
        # Call the unified analysis function
        analysis = analyze_text_with_ai(pub.content)
        
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

