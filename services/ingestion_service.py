from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any
import json

from core.models import AcademicMember, ResearcherDetails, Publication, ExternalMetric, IngestionAudit
from services.scraper_service import get_openalex_metrics, get_semantic_scholar_metrics
from services import publication_service
from services import journal_service
from services.openalex_service import get_publication_by_doi, extract_publication_metadata
import os

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

    def process_pdf_ingestion(self, file_content: bytes, filename: str, db: Session, skip_ai: bool = False) -> Dict[str, Any]:
        """
        Orchestrate PDF ingestion process: Validation -> Upload -> Enrichment -> Save.
        """
        # 1. Validate PDF
        is_valid, error_msg = publication_service.validate_pdf_file(filename, file_content)
        if not is_valid:
            raise ValueError(error_msg)
        
        clean_title = filename.replace('.pdf', '').replace('_', ' ')
        
        # 2. Check duplicate by title
        existing_pub = db.query(Publication).filter(
            Publication.title == clean_title
        ).first()
        
        if existing_pub:
            return {
                "id": existing_pub.id,
                "status": "duplicate",
                "message": f"Publication duplicate: ID {existing_pub.id}"
            }
        
        # 3. Enrich data (Parses PDF, Extracts Authors/DOI)
        # FASE 1: Solo metadatos desde OpenAlex (SIN análisis de IA)
        # La IA se ejecutará después manualmente via endpoint /generate-summaries
        enriched_data = publication_service.enrich_publication_data(
            file_content, 
            filename, 
            db, 
            skip_ai=True  # ← SIEMPRE True ahora (FASE 1 simplificada)
        )
        
        # 3.5 Check duplicate by DOI (Prevent IntegrityError)
        if enriched_data.get("doi"):
            existing_by_doi = db.query(Publication).filter(
                Publication.canonical_doi == enriched_data["doi"]
            ).first()
            
            if existing_by_doi:
                return {
                    "id": existing_by_doi.id,
                    "status": "duplicate",
                    "message": f"Publication duplicate by DOI: {enriched_data['doi']}"
                }

        # 4. Save PDF file to disk
        pdf_directory = "data/publications"
        os.makedirs(pdf_directory, exist_ok=True)
        safe_filename = filename.replace(' ', '_').replace('/', '_')
        file_path = os.path.join(pdf_directory, safe_filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        print(f"   [Ingestion] Saved PDF to: {file_path}")
        
        # Determine authors string
        author_names = []
        if enriched_data["matched_author_ids"]:
            authors = db.query(AcademicMember).filter(
                AcademicMember.id.in_(enriched_data["matched_author_ids"])
            ).all()
            author_names = [a.full_name for a in authors]
        
        autores_str = ", ".join(author_names) if author_names else "Unknown Authors"
        
        # 5. Smart Year Detection + Metrics from OpenAlex
        publication_year = str(datetime.now().year)  # Fallback
        metrics_data = None
        canonical_doi_value = enriched_data.get("doi")
        doi_verification_status = "pending"
        
        if canonical_doi_value:
            try:
                print(f"   [Ingestion] Fetching OpenAlex metadata for DOI: {canonical_doi_value}")
                openalex_data = get_publication_by_doi(canonical_doi_value)
                metrics_data = extract_publication_metadata(openalex_data)
                doi_verification_status = "valid_openalex"
                
                # Extract year and title from OpenAlex
                if metrics_data:
                    if metrics_data.get("publication_year"):
                        publication_year = str(metrics_data["publication_year"])
                    if metrics_data.get("title"):
                        clean_title = metrics_data["title"]

            except Exception as e:
                print(f"   [Ingestion] ⚠️ Could not fetch OpenAlex metadata: {e}")
        
        # 6. Extract ORCIDs from PDF hyperlinks
        try:
            from services.orcid_metadata_service import extract_orcids_from_pdf_hyperlinks
            # Note: We just extract for now, full enrichment usually happens if we want to create users.
            # But the current controller just printed it? 
            # Controller code: "author_metadata = enrich_orcids_with_metadata(orcids_list)"
            # It didn't seem to USE it for the Publication creation?
            # Let's check logic. It printed "Found ... ORCIDs". And "author_metadata".
            # It seems it was for debugging or future use?
            # I will include the extraction and print.
            orcids_list = extract_orcids_from_pdf_hyperlinks(file_content)
            if orcids_list:
                print(f"   [Ingestion] Found {len(orcids_list)} ORCIDs in PDF hyperlinks: {orcids_list}")
        except Exception as e:
            print(f"   [Ingestion] ⚠️ ORCID extraction warning: {e}")
        
        # 6.5 Extract Journal Name and Publisher from OpenAlex (NO vincular aún)
        detected_journal_name = None
        publisher = None
        
        try:
            # Obtener de OpenAlex
            if metrics_data and metrics_data.get("primary_location", {}).get("source"):
                 detected_journal_name = metrics_data["primary_location"]["source"].get("display_name")
                 publisher = metrics_data["primary_location"]["source"].get("host_organization_name")
                 print(f"   [Ingestion] Journal from OpenAlex: {detected_journal_name} ({publisher})")
        except Exception as e:
            print(f"   [Ingestion] ⚠️ Journal extraction failed: {e}")

        # 7. Create Publication Record (FASE 1: Solo metadata)
        new_pub = Publication(
            title=clean_title,
            year=publication_year,
            journal_id=None,  # ← NO vincular aún (se hará en FASE 3)
            url=enriched_data.get("doi") or clean_title, 
            authors=autores_str,
            local_path=file_path,
            
            # Resúmenes vacíos (se generan en FASE 2)
            summary_es=None,
            summary_en=None,
            
            # Campos de OpenAlex
            canonical_doi=canonical_doi_value,
            doi_verification_status=doi_verification_status,
            metrics_data=metrics_data,
            
            # NUEVOS CAMPOS
            enrichment_status="metadata_only",  # ← Estado inicial
            journal_name_temp=detected_journal_name,  # ← Guardar temporalmente
            publisher_temp=publisher,  # ← Guardar temporalmente
        )
        # Wait, if `content` is huge, verification needed.
        new_pub.content = enriched_data.get("text", "")  # Assign full extracted text
        
        db.add(new_pub)
        db.commit()
        db.refresh(new_pub)
        
        # 8. Create Researcher Connections
        for member_id in enriched_data["matched_author_ids"]:
            from core.models import ResearcherPublication 
            conn = ResearcherPublication(
                publication_id=new_pub.id,
                member_id=member_id,
                match_method="auto_ai" if not skip_ai else "auto_keyword",
                match_score=enriched_data.get("match_score", 80)
            )
            db.add(conn)
        
        db.commit()
        
        # 9. RAG Indexing
        rag_indexed = False
        try:
            from services.rag_service import get_semantic_engine
            if new_pub.content and len(new_pub.content) > 100:
                engine = get_semantic_engine()
                # Assuming process_single_publication returns dict with 'success'
                rag_result = engine.process_single_publication(new_pub.id)
                rag_indexed = rag_result.get("success", False)
                print(f"   [Ingestion] RAG Indexed: {rag_indexed}")
        except Exception as e:
            print(f"   [Ingestion] ⚠️ RAG Indexing failed: {e}")
        
        return {
            "id": new_pub.id,
            "status": "success",
            "message": f"Publication uploaded: {clean_title}",
            "rag_indexed": rag_indexed
        }
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
