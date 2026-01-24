

# ==============================================================================
# SCHOLAR INTELLIGENCE ENRICHMENT
# ==============================================================================

@router.post("/{pub_id}/enrich-scholar")
async def enrich_publication_with_scholar(
    pub_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Enrich a publication with Scholar API data (embeddings, citations, TLDR).
    
    Args:
        pub_id: Publication ID
        force: Force re-enrichment even if cached data exists (default: False)
        
    Returns:
        Enrichment result with Scholar data
    """
    from services.scholar_enrichment import ScholarEnrichmentService
    
    try:
        service = ScholarEnrichmentService(db)
        result = await service.enrich_publication(pub_id)
        
        return {
            "publication_id": pub_id,
            **result
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Enrichment error: {str(e)}")


@router.post("/batch-enrich-scholar")
async def batch_enrich_publications_with_scholar(
    publication_ids: List[int] = Body(..., embed=True),
    skip_cached: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Enrich multiple publications with Scholar data in batch.
    
    Args:
        publication_ids: List of publication IDs to enrich
        skip_cached: Skip publications already enriched (default: True)
        
    Returns:
        Summary of batch enrichment results
    """
    from services.scholar_enrichment import ScholarEnrichmentService
    
    try:
        service = ScholarEnrichmentService(db)
        results = await service.batch_enrich(publication_ids, skip_cached=skip_cached)
        
        return results
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Batch enrichment error: {str(e)}")


@router.get("/{pub_id}/scholar-data")
async def get_publication_scholar_data(
    pub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get cached Scholar data for a publication.
    
    Returns enrichment status and data if available.
    """
    from core.models import ScholarPaperData
    
    # Get publication
    pub = db.query(Publication).filter(Publication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    if not pub.canonical_doi:
        return {
            "status": "no_doi",
            "message": "Publication has no DOI"
        }
    
    # Get Scholar data
    scholar_data = db.query(ScholarPaperData).filter(
        ScholarPaperData.doi == pub.canonical_doi
    ).first()
    
    if not scholar_data:
        return {
            "status": "not_enriched",
            "message": "No Scholar data available. Run enrichment first."
        }
    
    return {
        "status": scholar_data.enrichment_status.value,
        "doi": scholar_data.doi,
        "semantic_scholar_id": scholar_data.semantic_scholar_id,
        "title": scholar_data.title,
        "year": scholar_data.year,
        "authors": scholar_data.authors,
        "tldr": scholar_data.tldr,
        "abstract": scholar_data.abstract,
        "embedding_dimensions": len(scholar_data.embedding_vector) if scholar_data.embedding_vector else 0,
        "citation_count": scholar_data.citation_count,
        "intent_breakdown": scholar_data.intent_breakdown,
        "smart_citations": scholar_data.smart_citations,
        "reference_graph": {
            "nodes": scholar_data.reference_nodes,
            "links": scholar_data.reference_links
        } if scholar_data.reference_nodes else None,
        "last_enriched_at": scholar_data.last_enriched_at.isoformat() if scholar_data.last_enriched_at else None,
        "error_message": scholar_data.error_message
    }
