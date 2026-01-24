"""
Export Routes - Endpoints for exporting data in various formats
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel

from database.session import get_db
from core.models import Publication, ScholarPaperData, Journal, JournalCategory, ResearcherPublication, AcademicMember
from api.routes.auth import get_current_user
import logging

router = APIRouter(prefix="/exports", tags=["Exports"])
logger = logging.getLogger(__name__)


class PublicationMetrics(BaseModel):
    id: int
    title: str
    doi: Optional[str]
    year: Optional[str]
    authors: Optional[str]
    quartile: Optional[str]
    percentile: Optional[float]
    jif: Optional[float]
    sjr: Optional[float]
    citescore: Optional[float]
    citation_count: int
    is_top_10_percent: bool
    journal_name: Optional[str]
    category: Optional[str]
    publisher: Optional[str]


def get_best_category(journal: Journal) -> Optional[JournalCategory]:
    """Get the category with the highest percentile from a journal"""
    if not journal or not journal.categories:
        return None

    # Sort by percentile descending, then by quartile quality (Q1 > Q2 > Q3 > Q4)
    quartile_map = {'Q1': 4, 'Q2': 3, 'Q3': 2, 'Q4': 1}

    sorted_cats = sorted(
        journal.categories,
        key=lambda c: (
            c.percentile if c.percentile is not None else 0,
            quartile_map.get(c.quartile, 0)
        ),
        reverse=True
    )

    return sorted_cats[0] if sorted_cats else None


@router.get("/publications-metrics", response_model=List[PublicationMetrics])
def get_publications_metrics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all publications with their metrics for Excel export.
    Uses the same data structure as /public/publications for consistency.
    """

    # Eager load all relationships (same as /public/publications)
    publications = (
        db.query(Publication)
        .options(
            joinedload(Publication.researcher_connections)
            .joinedload(ResearcherPublication.member)
            .joinedload(AcademicMember.researcher_details),
            joinedload(Publication.journal).joinedload(Journal.categories)
        )
        .order_by(Publication.id.desc())
        .all()
    )

    # Get all scholar data for citations
    scholar_data_map = {}
    scholar_entries = db.query(ScholarPaperData).all()
    for entry in scholar_entries:
        if entry.publication_id:
            scholar_data_map[entry.publication_id] = entry

    results = []

    for pub in publications:
        try:
            # Get authors as comma-separated string
            authors_list = []
            for rp in pub.researcher_connections:
                if rp.member:
                    authors_list.append(rp.member.full_name)
            authors_str = ", ".join(authors_list) if authors_list else pub.authors

            # Get Scholar citation count
            scholar = scholar_data_map.get(pub.id)
            citation_count = scholar.citation_count if scholar else 0

            # Determine quartile, percentile, and journal metrics
            # Priority order: impact_metrics > wos_verification > journal categories > quartile field > ai_journal_analysis
            quartile = None
            percentile = None
            jif = None
            sjr = None
            citescore = None
            journal_name = None
            category = None
            publisher = None

            # Priority 1: impact_metrics (legacy WOS Match data)
            if hasattr(pub, 'impact_metrics') and pub.impact_metrics:
                try:
                    quartile = getattr(pub.impact_metrics, 'quartile', None) or quartile
                    jif = getattr(pub.impact_metrics, 'jif', None) or jif
                    percentile = getattr(pub.impact_metrics, 'ranking_percentile', None) or percentile
                except:
                    pass

            # Priority 2: wos_verification
            if hasattr(pub, 'wos_verification') and pub.wos_verification:
                try:
                    wos_quartile = getattr(pub.wos_verification, 'quartile', None)
                    wos_decile = getattr(pub.wos_verification, 'decile', None)

                    if wos_quartile:
                        quartile = wos_quartile

                    # Calculate percentile from decile (decile 1 = top 10% = 90-100 percentile)
                    if wos_decile and not percentile:
                        percentile = (11 - wos_decile) * 10 - 5  # Mid-point of decile range

                    # Get journal name from WOS verification
                    journal_name = getattr(pub.wos_verification, 'journal_name', None) or journal_name
                except:
                    pass

            # Priority 3: Journal with categories
            if pub.journal:
                journal_name = pub.journal.name or journal_name
                publisher = pub.journal.publisher or publisher
                jif = pub.journal.jif_current or jif
                sjr = pub.journal.scopus_sjr or sjr
                citescore = pub.journal.scopus_citescore or citescore

                # Get best category (highest percentile)
                best_cat = get_best_category(pub.journal)
                if best_cat:
                    quartile = best_cat.quartile or quartile
                    percentile = best_cat.percentile or percentile
                    category = best_cat.category_name

            # Priority 4: Direct quartile field on publication
            if not quartile and hasattr(pub, 'quartile'):
                quartile = pub.quartile

            # Priority 5: AI journal analysis fallback
            if not quartile and hasattr(pub, 'ai_journal_analysis') and pub.ai_journal_analysis:
                try:
                    quartile = pub.ai_journal_analysis.get('quartile_estimate') or quartile
                except:
                    pass

            # Fallback to temp journal fields
            if not journal_name:
                journal_name = pub.journal_name_temp
            if not publisher:
                publisher = pub.publisher_temp

            # Determine if Top 10%
            # Criteria 1: Percentile >= 90
            # Criteria 2: WOS verification is_top_10 flag
            # Criteria 3: Q1 + citations > 10
            is_top_10 = False

            if percentile and percentile >= 90:
                is_top_10 = True

            if hasattr(pub, 'wos_verification') and pub.wos_verification:
                if getattr(pub.wos_verification, 'is_top_10', False):
                    is_top_10 = True

            if quartile == 'Q1' and citation_count >= 10:
                is_top_10 = True

            results.append(PublicationMetrics(
                id=pub.id,
                title=pub.title,
                doi=pub.canonical_doi,
                year=pub.year,
                authors=authors_str,
                quartile=quartile,
                percentile=percentile,
                jif=jif,
                sjr=sjr,
                citescore=citescore,
                citation_count=citation_count,
                is_top_10_percent=is_top_10,
                journal_name=journal_name,
                category=category,
                publisher=publisher
            ))

        except Exception as e:
            logger.warning(f"Error processing publication {pub.id} for export: {e}")
            continue

    # Sort by citation count descending
    results.sort(key=lambda x: x.citation_count, reverse=True)

    return results
