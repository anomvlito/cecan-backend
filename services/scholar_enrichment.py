"""
Scholar Enrichment Service
Orchestrates fetching paper data from Semantic Scholar API and caching in database.
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

from core.models import Publication, ScholarPaperData, ScholarEnrichmentStatus
from modules.scholar.client import SemanticScholarClient
import os

logger = logging.getLogger(__name__)


class ScholarEnrichmentService:
    """Service for enriching publications with Scholar data."""
    
    def __init__(self, db: Session):
        self.db = db
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.scholar_client = SemanticScholarClient(api_key=api_key)
    
    async def enrich_publication(self, publication_id: int) -> Dict[str, Any]:
        """
        Enrich a single publication with Scholar data.
        
        Args:
            publication_id: ID of publication to enrich
            
        Returns:
            Dict with enrichment results and status
        """
        # Get publication
        publication = self.db.query(Publication).filter(Publication.id == publication_id).first()
        if not publication:
            return {"error": "Publication not found", "status": "not_found"}
        
        if not publication.canonical_doi:
            return {"error": "Publication has no DOI", "status": "no_doi"}
        
        doi = publication.canonical_doi
        
        # Check if already enriched recently (cache for 30 days)
        existing = self.db.query(ScholarPaperData).filter(ScholarPaperData.doi == doi).first()
        if existing and existing.enrichment_status == ScholarEnrichmentStatus.ENRICHED:
            days_old = (datetime.utcnow() - existing.last_enriched_at).days if existing.last_enriched_at else 999
            if days_old < 30:
                logger.info(f"Using cached Scholar data for DOI {doi} (age: {days_old} days)")
                return {
                    "status": "cached",
                    "doi": doi,
                    "data": self._scholar_data_to_dict(existing)
                }
        
        # Fetch from Scholar API
        try:
            logger.info(f"Fetching Scholar data for DOI {doi}")
            scholar_data = await self.scholar_client.get_paper_intelligence(doi)
            
            # Check if paper was found
            if scholar_data.get("paperId") == "NOT_FOUND":
                self._update_or_create_scholar_data(
                    doi, publication_id, 
                    status=ScholarEnrichmentStatus.NOT_FOUND,
                    error_message="Paper not found in Semantic Scholar"
                )
                return {"error": "Paper not found in Semantic Scholar", "status": "not_found"}
            
            # Fetch genealogy graph
            genealogy_data = await self.scholar_client.get_paper_genealogy(doi)
            
            # Save to database
            scholar_record = self._update_or_create_scholar_data(
                doi=doi,
                publication_id=publication_id,
                scholar_data=scholar_data,
                genealogy_data=genealogy_data,
                status=ScholarEnrichmentStatus.ENRICHED
            )
            
            logger.info(f"Successfully enriched publication {publication_id} with Scholar data")
            
            return {
                "status": "enriched",
                "doi": doi,
                "data": self._scholar_data_to_dict(scholar_record)
            }
            
        except Exception as e:
            logger.error(f"Error enriching publication {publication_id}: {str(e)}")
            self._update_or_create_scholar_data(
                doi, publication_id,
                status=ScholarEnrichmentStatus.FAILED,
                error_message=str(e)
            )
            return {"error": str(e), "status": "failed"}
    
    async def batch_enrich(self, publication_ids: List[int], skip_cached: bool = True) -> Dict[str, Any]:
        """
        Enrich multiple publications in batch.
        
        Args:
            publication_ids: List of publication IDs to enrich
            skip_cached: Skip publications already enriched (default: True)
            
        Returns:
            Summary of batch enrichment results
        """
        results = {
            "total": len(publication_ids),
            "enriched": 0,
            "cached": 0,
            "failed": 0,
            "not_found": 0,
            "no_doi": 0,
            "details": []
        }
        
        for pub_id in publication_ids:
            result = await self.enrich_publication(pub_id)
            status = result.get("status", "unknown")
            
            results["details"].append({
                "publication_id": pub_id,
                "status": status,
                "doi": result.get("doi"),
                "error": result.get("error")
            })
            
            # Update counters
            if status == "enriched":
                results["enriched"] += 1
            elif status == "cached":
                results["cached"] += 1
            elif status == "failed":
                results["failed"] += 1
            elif status == "not_found":
                results["not_found"] += 1
            elif status == "no_doi":
                results["no_doi"] += 1
        
        return results
    
    def _update_or_create_scholar_data(
        self,
        doi: str,
        publication_id: int,
        scholar_data: Optional[Dict[str, Any]] = None,
        genealogy_data: Optional[Dict[str, Any]] = None,
        status: ScholarEnrichmentStatus = ScholarEnrichmentStatus.PENDING,
        error_message: Optional[str] = None
    ) -> ScholarPaperData:
        """Update existing or create new Scholar data record."""
        
        existing = self.db.query(ScholarPaperData).filter(ScholarPaperData.doi == doi).first()
        
        if existing:
            record = existing
        else:
            record = ScholarPaperData(doi=doi, publication_id=publication_id)
            self.db.add(record)
        
        # Update fields
        record.enrichment_status = status
        record.error_message = error_message
        record.updated_at = datetime.utcnow()
        
        if status == ScholarEnrichmentStatus.ENRICHED:
            record.last_enriched_at = datetime.utcnow()
        
        # Populate data if provided
        if scholar_data:
            record.semantic_scholar_id = scholar_data.get("paperId")
            record.title = scholar_data.get("title")
            record.year = scholar_data.get("year")
            record.authors = scholar_data.get("authors")
            record.tldr = scholar_data.get("tldr")
            record.abstract = scholar_data.get("abstract")
            
            # Extract full embedding vector (768 dimensions)
            # Client now returns it directly as 'embedding' field
            embedding_vector = scholar_data.get("embedding")
            if embedding_vector and isinstance(embedding_vector, list):
                record.embedding_vector = embedding_vector
            
            record.citation_count = len(scholar_data.get("smart_citations", []))
            record.intent_breakdown = scholar_data.get("intent_breakdown")
            record.smart_citations = scholar_data.get("smart_citations")
        
        if genealogy_data:
            record.reference_nodes = genealogy_data.get("nodes")
            record.reference_links = genealogy_data.get("links")
        
        self.db.commit()
        self.db.refresh(record)
        
        return record
    
    def _scholar_data_to_dict(self, record: ScholarPaperData) -> Dict[str, Any]:
        """Convert ScholarPaperData model to dictionary."""
        return {
            "doi": record.doi,
            "semantic_scholar_id": record.semantic_scholar_id,
            "title": record.title,
            "year": record.year,
            "authors": record.authors,
            "tldr": record.tldr,
            "abstract": record.abstract,
            "embedding_dimensions": len(record.embedding_vector) if record.embedding_vector else 0,
            "citation_count": record.citation_count,
            "intent_breakdown": record.intent_breakdown,
            "smart_citations_count": len(record.smart_citations) if record.smart_citations else 0,
            "has_genealogy": bool(record.reference_nodes),
            "enrichment_status": record.enrichment_status.value,
            "last_enriched_at": record.last_enriched_at.isoformat() if record.last_enriched_at else None
        }
