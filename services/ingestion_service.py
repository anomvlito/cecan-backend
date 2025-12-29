from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any
import json

from core.models import AcademicMember, ResearcherDetails, Publication, ExternalMetric, IngestionAudit
from services.scraper_service import get_openalex_metrics, get_semantic_scholar_metrics

class IngestionService:
    """Service to orchestrate data ingestion from external APIs."""

    def sync_researcher_metrics(self, db: Session, member_id: int) -> Dict[str, Any]:
        """
        Fetch and update metrics for a specific researcher.
        """
        researcher = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
        if not researcher or not researcher.researcher_details:
            return {"status": "skipped", "reason": "Not a researcher or no details found"}

        details = researcher.researcher_details
        results = []

        # 1. Sync from OpenAlex (Author level via ORCID)
        if details.orcid:
            metrics = get_openalex_metrics(orcid=details.orcid)
            if metrics:
                self._upsert_metric(db, member_id, None, "openalex", "h_index", metrics.get("h_index", 0))
                self._upsert_metric(db, member_id, None, "openalex", "citation_count", metrics.get("citation_count", 0))
                self._upsert_metric(db, member_id, None, "openalex", "i10_index", metrics.get("i10_index", 0))
                
                # Update legacy fields for immediate display in current frontend
                details.indice_h = metrics.get("h_index", 0)
                details.citaciones_totales = metrics.get("citation_count", 0)
                db.add(details) # Ensure update is tracked
                
                results.append("openalex_author_sync_ok")

        # 2. Sync Publications (Work level via DOI)
        # Get all publications for this researcher that have a DOI
        pubs = db.query(Publication).join(Publication.researcher_connections).filter(
            Publication.researcher_connections.any(member_id=member_id),
            Publication.url_origen.like("%doi.org%") # Heuristic for DOI presence
        ).all()

        for pub in pubs:
            doi = pub.url_origen # Assuming DOI is stored here or extracted
            if not doi: continue

            # Semantic Scholar
            ss_metrics = get_semantic_scholar_metrics(doi)
            if ss_metrics:
                self._upsert_metric(db, None, pub.id, "semanticscholar", "citation_count", ss_metrics.get("citation_count", 0))
                results.append(f"ss_pub_{pub.id}_ok")
            
            # OpenAlex (Work level)
            oa_metrics = get_openalex_metrics(doi=doi)
            if oa_metrics:
                self._upsert_metric(db, None, pub.id, "openalex", "citation_count", oa_metrics.get("citation_count", 0))
                results.append(f"oa_pub_{pub.id}_ok")

        return {"status": "success", "synced": results}

    def _upsert_metric(self, db: Session, member_id: int | None, pub_id: int | None, source: str, metric_type: str, value: float):
        """
        Logical Upsert: Updates value if source/type exists for the entity, else inserts.
        """
        query = db.query(ExternalMetric).filter(
            ExternalMetric.source == source,
            ExternalMetric.metric_type == metric_type
        )
        
        if member_id:
            query = query.filter(ExternalMetric.member_id == member_id)
        elif pub_id:
            query = query.filter(ExternalMetric.publication_id == pub_id)
        else:
            return

        existing = query.first()
        if existing:
            existing.value = value
            existing.last_updated = datetime.utcnow()
        else:
            new_metric = ExternalMetric(
                member_id=member_id,
                publication_id=pub_id,
                source=source,
                metric_type=metric_type,
                value=value
            )
            db.add(new_metric)
        db.commit()

    def run_weekly_sync(self, db: Session) -> Dict[str, Any]:
        """
        Orchestrates full sync for all active researchers.
        """
        print(f"[{datetime.utcnow()}] Starting weekly external metrics sync...")
        researchers = db.query(AcademicMember).filter(AcademicMember.member_type == 'researcher', AcademicMember.is_active == True).all()
        
        summary = {
            "total_researchers": len(researchers),
            "processed": 0,
            "errors": 0,
            "details": []
        }

        for r in researchers:
            try:
                res = self.sync_researcher_metrics(db, r.id)
                summary["processed"] += 1
                summary["details"].append({"id": r.id, "name": r.full_name, "res": res})
            except Exception as e:
                summary["errors"] += 1
                summary["details"].append({"id": r.id, "error": str(e)})

        # Log to IngestionAudit
        audit = IngestionAudit(
            action="weekly_external_sync",
            status="success" if summary["errors"] == 0 else "partial",
            payload_summary=json.dumps({
                "processed": summary["processed"],
                "errors": summary["errors"],
                "total": summary["total_researchers"]
            })
        )
        db.add(audit)
        db.commit()

        print(f"[{datetime.utcnow()}] Sync completed. Processed: {summary['processed']}, Errors: {summary['errors']}")
        return summary

# Global instance
ingestion_service = IngestionService()
