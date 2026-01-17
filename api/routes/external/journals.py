"""
Journal Search Routes - WOS Mirror and OpenAlex Search
"""

from fastapi import APIRouter, Query, Depends, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, List

from database.session import get_db
from core.models import WosJournalMirror

router = APIRouter(tags=["External Metrics"])


async def search_wos_mirror(
    query: str,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Search the local WOS Mirror database for journals.
    Reads from the wos_journal_mirror table populated by the scraper.

    This function is also used by analysis.py for triangulation.
    """
    q = query.strip()

    # Search logic: Exact match for ISSN, Fuzzy for Name
    # We use ILIKE for case-insensitive search

    # Detect if query looks like ISSN (digit-digit)
    is_mostly_digits =  sum(c.isdigit() for c in q) > 3

    base_query = db.query(WosJournalMirror)

    if is_mostly_digits:
         results = base_query.filter(
            or_(
                WosJournalMirror.issn.ilike(f"%{q}%"),
                WosJournalMirror.eissn.ilike(f"%{q}%")
            )
        ).limit(20).all()
    else:
        results = base_query.filter(
            WosJournalMirror.journal_name.ilike(f"%{q}%")
        ).limit(20).all()

    return [
        {
            "id": r.wos_id,
            "journal_name": r.journal_name,
            "issn": r.issn,
            "eissn": r.eissn,
            "best_quartile": r.best_quartile,
            "best_ranking_percent": r.best_ranking_percent,
            "jif": r.jif,
            "jif_5year": r.five_year_jif,
            "categories": r.categories,
            "ranking_category": r.ranking_category, # Added logic to expose this field
            "publisher": r.publisher,
            "source_url": r.source_url
        }
        for r in results
    ]


@router.get("/wos-mirror/search")
async def search_wos_mirror_endpoint(
    query: str = Query(..., min_length=2, description="Journal Name or ISSN"),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Search the local WOS Mirror database for journals.
    Reads from the wos_journal_mirror table populated by the scraper.
    """
    return await search_wos_mirror(query=query, db=db)



@router.post("/openalex/search-journals")
async def search_openalex_journals(
    payload: Dict[str, str] = Body(..., examples=[{"title": "Nature"}])
) -> List[Dict[str, Any]]:
    """
    Search for JOURNALS (Sources) in OpenAlex.
    Useful for cross-validation with WOS Mirror.
    """
    import requests
    query = payload.get("title", "").strip()
    if not query:
        return []

    url = "https://api.openalex.org/sources"
    params = {
        "search": query,
        "filter": "type:journal", # Fixed: was bg_filter
        "per_page": 10,
        "mailto": "admin@cecan.cl"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            print(f"OpenAlex Error: {r.status_code}")
            return []

        data = r.json()
        results = []

        for item in data.get("results", []):
            # Extract relevant metrics
            metrics = item.get("summary_stats", {})

            # Extract ISSNs
            issn_l = item.get("issn_l")
            issns = item.get("issn", [])

            # Map to our standard format
            journal = {
                "id": item.get("id"),
                "journal_name": item.get("display_name"),
                "publisher": item.get("host_organization_name"),
                "issn": issn_l,
                "eissn": issns[0] if issns else None,
                "country": item.get("country_code"),
                "impact_factor_2yr": metrics.get("2yr_mean_citedness"),
                "h_index": metrics.get("h_index"),
                "works_count": item.get("works_count"),
                "cited_by_count": item.get("cited_by_count"),
                "homepage_url": item.get("homepage_url"),
                "source": "openalex"
            }
            results.append(journal)

        return results

    except Exception as e:
        print(f"OpenAlex Exception: {e}")
        return []
