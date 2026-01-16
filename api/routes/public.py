from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from database.session import get_db
from core.models import AcademicMember, ResearcherDetails, Project, Publication, ResearcherPublication, WorkPackage, Journal, JournalCategory
from schemas import PublicationSummarySchema, ResearcherSummarySchema
from services.graph_service import build_graph_data

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
    canonical_doi: Optional[str] = None  # Added for frontend compatibility
    doi_verification_status: Optional[str] = None # pending, valid_openalex, valid_http, broken, repaired
    has_funding_ack: bool = False
    anid_report_status: str = "Pending"
    # OpenAlex metrics
    metrics_data: Optional[dict] = None
    metrics_last_updated: Optional[datetime] = None
    # AI-generated summaries  
    summary_es: Optional[str] = None
    summary_en: Optional[str] = None
    ai_journal_analysis: Optional[dict] = None  # Added: AI Journal Analysis
    quartile: Optional[str] = None  # Added: Dedicated Quartile Column
    content: Optional[str] = None
    journal: Optional[dict] = None  # ✅ ADDED: Journal data with categories
    # Temporary journal fields (NEW)
    journal_name_temp: Optional[str] = None
    publisher_temp: Optional[str] = None
    # Enrichment status (NEW)
    enrichment_status: str = "metadata_only"
    # WOS Verification (NEW)
    wos_verification: Optional[dict] = None
    # Legacy impact metrics
    impact_metrics: Optional[dict] = None
    authors: List[ResearcherSummarySchema] = []



# --- Endpoints ---

@router.get("/researchers", response_model=List[PublicResearcherOut])
async def get_public_researchers(db: Session = Depends(get_db)):
    """
    Get public list of researchers with sanitized fields.
    """
    try:
        # Fetch researchers with details and WP
        researchers = (
            db.query(AcademicMember)
            .options(
                joinedload(AcademicMember.researcher_details),
                joinedload(AcademicMember.wp)
            )
            .filter(AcademicMember.member_type == 'researcher')
            .filter(AcademicMember.is_active == True)
            .all()
        )
        
        results = []
        for member in researchers:
            details = member.researcher_details
            wp = member.wp
            
            # Fetch publications
            pubs = []
            if member.publication_connections:
                for rp in member.publication_connections:
                    pub = rp.publication
                    pubs.append({
                        "id": pub.id,
                        "title": pub.title,
                        "year": pub.year,
                        "url": pub.url,
                        "doi": pub.canonical_doi, # Map to standardized field
                        "canonical_doi": pub.canonical_doi, # Map to field expected by table
                        "has_funding_ack": pub.has_funding_ack,
                        "anid_report_status": pub.anid_report_status or "Pending"
                    })
            
            results.append({
                "id": member.id,
                "full_name": member.full_name,
                "photo_url": details.url_foto if details else None,
                "category": details.category if details else None,
                "wp_name": wp.name if wp else None,
                "metrics": {
                    "h_index": details.indice_h if details else None,
                    "total_citations": details.citaciones_totales if details else None
                },
                "publications": pubs
            })
            
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching researchers: {str(e)}")


import logging
# Ensure logger is configured
logger = logging.getLogger(__name__)

@router.get("/publications", response_model=List[PublicPublicationOut])
async def get_public_publications(db: Session = Depends(get_db)):
    """
    Get public list of publications with authors.
    Optimized to avoid N+1 queries and handle missing schema columns safely.
    """
    try:
        # 1. Eager loading: Fetch publication, connection, member, AND journal
        publications = (
            db.query(Publication)
            .options(
                joinedload(Publication.researcher_connections)
                .joinedload(ResearcherPublication.member)
                .joinedload(AcademicMember.researcher_details),
                joinedload(Publication.journal).joinedload(Journal.categories)  # Load journal and its categories
            )
            .order_by(Publication.id.desc())
            .all()
        )
        
        results = []
        for pub in publications:
            try:
                authors = []
                # Iterate over connections already loaded in memory
                for rp in pub.researcher_connections:
                    if not rp.member: continue # Skip if data is corrupt
                    
                    member = rp.member
                    details = member.researcher_details
                    
                    authors.append({
                        "id": member.id,
                        "full_name": member.full_name,
                        # Safe navigation to avoid error if details is None
                        "avatar_url": details.url_foto if details else None
                    })
                
                # Serialize journal if exists
                journal_data = None
                if pub.journal:
                    try:
                        journal_data = {
                            "id": pub.journal.id,
                            "name": pub.journal.name,
                            "publisher": pub.journal.publisher,
                            "jif_current": pub.journal.jif_current,
                            "jif_year": pub.journal.jif_year,
                            "jif_5year": pub.journal.jif_5year,
                            "scopus_citescore": pub.journal.scopus_citescore,
                            "scopus_sjr": pub.journal.scopus_sjr,
                            "scopus_snip": pub.journal.scopus_snip,
                            "last_updated": pub.journal.last_updated,
                            "categories": [
                                {
                                    "category_name": cat.category_name,
                                    "source": cat.source,
                                    "quartile": cat.quartile,
                                    "percentile": cat.percentile,
                                    "ranking": cat.ranking
                                }
                                for cat in pub.journal.categories
                            ] if pub.journal.categories else []
                        }
                    except Exception as e:
                        logger.warning(f"Error serializing journal for publication {pub.id}: {e}")
                        journal_data = None
                
                # Safe access to impact metrics
                impact_metrics_data = None
                if hasattr(pub, 'impact_metrics') and pub.impact_metrics:
                    try:
                        impact_metrics_data = {
                            "citation_count": getattr(pub.impact_metrics, 'citation_count', None),
                            "is_international_collab": getattr(pub.impact_metrics, 'is_international_collab', None),
                            "quartile": getattr(pub.impact_metrics, 'quartile', None),
                            "jif": getattr(pub.impact_metrics, 'jif', None),
                            "ranking_percentile": getattr(pub.impact_metrics, 'ranking_percentile', None),
                        }
                    except Exception as e:
                        logger.warning(f"Error serializing impact_metrics for publication {pub.id}: {e}")
                
                # Safe access to WOS verification
                wos_data = None
                if hasattr(pub, 'wos_verification') and pub.wos_verification:
                    try:
                        wos_data = {
                            "match_type": getattr(pub.wos_verification, 'match_type', None),
                            "quartile": getattr(pub.wos_verification, 'quartile', None),
                            "decile": getattr(pub.wos_verification, 'decile', None),
                            "is_top_10": getattr(pub.wos_verification, 'is_top_10', False),
                            "source_url": getattr(pub.wos_verification, 'source_url', None),
                            "categories": getattr(pub.wos_verification, 'categories', []),
                            "journal_name": getattr(pub.wos_verification, 'journal_name', None)
                        }
                    except Exception as e:
                        logger.warning(f"Error serializing wos_verification for publication {pub.id}: {e}")
                
                # Build publication response
                results.append({
                    "id": pub.id,
                    "title": pub.title,
                    "year": pub.year,
                    "url": pub.url,
                    "doi": getattr(pub, "canonical_doi", None), 
                    "canonical_doi": getattr(pub, "canonical_doi", None),
                    "doi_verification_status": getattr(pub, "doi_verification_status", "pending"),
                    "has_funding_ack": getattr(pub, "has_funding_ack", False),
                    "anid_report_status": getattr(pub, "anid_report_status", "Pending"),
                    # OpenAlex metrics
                    "metrics_data": getattr(pub, "metrics_data", None),
                    "metrics_last_updated": getattr(pub, "metrics_last_updated", None),
                    # AI-generated summaries
                    "summary_es": getattr(pub, "summary_es", None),
                    "summary_en": getattr(pub, "summary_en", None),
                    "ai_journal_analysis": getattr(pub, "ai_journal_analysis", None),
                    "quartile": getattr(pub, "quartile", None),
                    "content": getattr(pub, "content", None),
                    "journal": journal_data,
                    # Temporary journal fields
                    "journal_name_temp": getattr(pub, "journal_name_temp", None),
                    "publisher_temp": getattr(pub, "publisher_temp", None),
                    # Enrichment status
                    "enrichment_status": getattr(pub, "enrichment_status", "metadata_only"),
                    # WOS Verification
                    "wos_verification": wos_data,
                    # Legacy impact metrics
                    "impact_metrics": impact_metrics_data,
                    "authors": authors
                })
                
            except Exception as e:
                # Log error but continue processing other publications
                logger.error(f"Error processing publication {pub.id}: {str(e)}", exc_info=True)
                # Optionally include a minimal entry or skip entirely
                continue
            
        return results
        
    except Exception as e:
        # Log real error to server console
        logger.error(f"CRITICAL ERROR in /public/publications: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/graph")
async def get_public_graph(db: Session = Depends(get_db)):
    """
    Get simplified graph data for public visualization.
    """
    try:
        data = build_graph_data(db)
        # We could filter sensitive data here if needed, but get_graph_data seems already safe enough for now
        # based on the legacy implementation.
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")
