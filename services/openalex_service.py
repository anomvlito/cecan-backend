"""
OpenAlex API Integration Service
- Fetches bibliometric metrics (H-Index, i10-Index, citations, works) for researchers via ORCID
- Fetches publication metrics (citations, journal info, collaborations) via DOI
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import AcademicMember, ResearcherDetails
from config import OPENALEX_CONTACT_EMAIL, OPENALEX_SYNC_THRESHOLD_DAYS


def fetch_metrics_by_orcid(orcid: str) -> Dict:
    """
    Fetch bibliometric metrics from OpenAlex API using ORCID.
    
    Args:
        orcid: ORCID identifier (can be full URL or just the ID)
        
    Returns:
        Dictionary with metrics: h_index, i10_index, works_count, cited_by_count
        
    Raises:
        HTTPException: If researcher not found or API error
    """
    # Clean ORCID (extract just the ID if full URL provided)
    clean_orcid = orcid.split('/')[-1].strip()
    
    # Build OpenAlex API URL
    url = f"https://api.openalex.org/authors/https://orcid.org/{clean_orcid}"
    
    # Headers for "Polite Pool" (faster, more reliable access)
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # Handle 404 - researcher not found
        if response.status_code == 404:
            raise HTTPException(
                status_code=404, 
                detail=f"Investigador con ORCID {clean_orcid} no encontrado en OpenAlex"
            )
        
        # Handle other errors
        if response.status_code != 200:
            raise HTTPException(
                status_code=502, 
                detail=f"Error de comunicación con OpenAlex (HTTP {response.status_code})"
            )
        
        data = response.json()
        
        # Extract metrics safely
        summary = data.get("summary_stats", {})
        
        return {
            "orcid": clean_orcid,
            "display_name": data.get("display_name", "Unknown"),
            "works_count": data.get("works_count", 0),
            "cited_by_count": data.get("cited_by_count", 0),
            "h_index": summary.get("h_index", 0),
            "i10_index": summary.get("i10_index", 0),
            "last_updated": data.get("updated_date", "")
        }
    
    except requests.Timeout:
        raise HTTPException(
            status_code=504, 
            detail="Timeout al conectar con OpenAlex. Intente nuevamente."
        )
    except requests.RequestException as e:
        print(f"Error conectando a OpenAlex: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Servicio de métricas temporalmente no disponible"
        )


def sync_all_researchers(db: Session, force_refresh: bool = False) -> Dict:
    """
    Synchronize OpenAlex metrics for all researchers with ORCID.
    
    Args:
        db: Database session
        force_refresh: If True, update all researchers. If False, only update 
                      those never synced or synced >30 days ago.
    
    Returns:
        Dictionary with sync summary:
        {
            "total_processed": int,
            "success": int,
            "skipped": int,
            "errors": int,
            "details": [{"name": str, "orcid": str, "status": str}, ...]
        }
    """
    # Query researchers with ORCID
    query = (
        db.query(AcademicMember, ResearcherDetails)
        .join(ResearcherDetails, AcademicMember.id == ResearcherDetails.member_id)
        .filter(AcademicMember.member_type == "researcher")
        .filter(ResearcherDetails.orcid.isnot(None))
        .filter(ResearcherDetails.orcid != "")
    )
    
    # Apply threshold filter if not forcing refresh
    if not force_refresh:
        threshold_date = datetime.utcnow() - timedelta(days=OPENALEX_SYNC_THRESHOLD_DAYS)
        query = query.filter(
            (ResearcherDetails.last_openalex_sync.is_(None)) |
            (ResearcherDetails.last_openalex_sync < threshold_date)
        )
    
    researchers = query.all()
    
    # Initialize counters
    total = len(researchers)
    success = 0
    skipped = 0
    errors = 0
    details = []
    
    print(f"[OpenAlex Sync] Processing {total} researchers (force_refresh={force_refresh})")
    
    for member, details_obj in researchers:
        try:
            # Fetch metrics from OpenAlex
            metrics = fetch_metrics_by_orcid(details_obj.orcid)
            
            # Update database fields
            details_obj.indice_h = metrics["h_index"]
            details_obj.i10_index = metrics["i10_index"]
            details_obj.works_count = metrics["works_count"]
            details_obj.citaciones_totales = metrics["cited_by_count"]
            details_obj.last_openalex_sync = datetime.utcnow()
            
            success += 1
            details.append({
                "name": member.full_name,
                "orcid": details_obj.orcid,
                "status": "updated",
                "h_index": metrics["h_index"],
                "citations": metrics["cited_by_count"]
            })
            
            print(f"  ✓ {member.full_name}: H-Index={metrics['h_index']}, Citas={metrics['cited_by_count']}")
            
            # Rate limiting: max 10 requests/second (100ms between requests)
            time.sleep(0.1)
            
        except HTTPException as e:
            errors += 1
            details.append({
                "name": member.full_name,
                "orcid": details_obj.orcid,
                "status": f"error: {e.detail}"
            })
            print(f"  ✗ {member.full_name}: {e.detail}")
            
        except Exception as e:
            errors += 1
            details.append({
                "name": member.full_name,
                "orcid": details_obj.orcid,
                "status": f"error: {str(e)}"
            })
            print(f"  ✗ {member.full_name}: Error inesperado - {str(e)}")
    
    # Commit all changes
    db.commit()
    
    print(f"[OpenAlex Sync] Completed: {success} success, {errors} errors")
    
    return {
        "total_processed": total,
        "success": success,
        "skipped": skipped,
        "errors": errors,
        "details": details
    }


# ===========================
# PUBLICATION METRICS (DOI)
# ===========================

import re
from tenacity import retry, stop_after_attempt, wait_exponential
import urllib.parse


def search_publication_by_title(title: str) -> Dict:
    """
    Search for a publication by title in OpenAlex.
    Returns the first best match if confidence is reasonable.
    """
    if not title or len(title) < 10:
        return None
        
    # Clean title for search
    clean_title = urllib.parse.quote(title)
    url = f"https://api.openalex.org/works?filter=title.search:{clean_title}&per_page=1"
    
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        print(f"   [OpenAlex] Searching details for title: {title[:50]}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                match = results[0]
                # Basic validation: Check if titles are somewhat similar?
                # OpenAlex search is usually good.
                print(f"   [OpenAlex] ✅ Found match by title: {match.get('doi')}")
                return {
                    "doi": match.get("doi"), # URL format
                    "openalex_id": match.get("id"),
                    "title": match.get("title"),
                    "publication_year": match.get("publication_year")
                }
    except Exception as e:
        print(f"   [OpenAlex] ⚠️ Search failed: {e}")
    
    return None


def extract_doi_from_url(url: str) -> str:
    """
    Extract clean DOI from URL or return as-is if already clean.
    
    Args:
        url: DOI URL or clean DOI
    
    Returns:
        Clean DOI string
    
    Examples:
        >>> extract_doi_from_url("https://doi.org/10.1038/nature12345")
        "10.1038/nature12345"
        >>> extract_doi_from_url("10.1038/nature12345")
        "10.1038/nature12345"
    """
    # Regex to extract DOI pattern
    pattern = r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)'
    match = re.search(pattern, url, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    # Return as-is if no match (might already be clean)
    return url.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def get_publication_by_doi(doi: str) -> Dict:
    """
    Query OpenAlex API for publication data by DOI.
    
    Args:
        doi: Clean DOI or DOI URL (e.g., "10.1038/nature12345")
    
    Returns:
        OpenAlex publication data dictionary
    
    Raises:
        HTTPException: If publication not found or API error
    
    Example:
        >>> data = get_publication_by_doi("10.1038/nature12345")
        >>> print(data["cited_by_count"])
        42
    """
    # Clean DOI (remove URL prefix if present)
    clean_doi = extract_doi_from_url(doi)
    
    url = f"https://api.openalex.org/works/doi:{clean_doi}"
    
    # Add email for polite pool (higher rate limits)
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        print(f"   [OpenAlex] Querying publication DOI: {clean_doi}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            openalex_id = data.get("id", "").split("/")[-1]
            print(f"   [OpenAlex] ✅ Found publication: {openalex_id}")
            return data
        elif response.status_code == 404:
            print(f"   [OpenAlex] ⚠️ DOI not found: {clean_doi}")
            raise HTTPException(
                status_code=404,
                detail=f"DOI {clean_doi} no encontrado en OpenAlex"
            )
        elif response.status_code == 429:
            print("   [OpenAlex] ⚠️ Rate limit hit, retrying...")
            raise Exception("Rate limit exceeded")  # Trigger retry
        else:
            print(f"   [OpenAlex] ❌ Error {response.status_code}: {response.text[:100]}")
            raise HTTPException(
                status_code=502,
                detail=f"Error de comunicación con OpenAlex (HTTP {response.status_code})"
            )
    
    except requests.exceptions.Timeout:
        print("   [OpenAlex] ⚠️ Request timeout")
        raise HTTPException(
            status_code=504,
            detail="Timeout al conectar con OpenAlex"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"   [OpenAlex] ❌ Error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Error consultando OpenAlex: {str(e)}"
        )



def fetch_journal_metrics(source_id: str) -> Dict:
    """
    Fetch comprehensive metrics for a journal/source from OpenAlex.
    
    Args:
        source_id: OpenAlex Source ID (e.g., "S123456789" or full URL)
        
    Returns:
        Dictionary with journal metrics (h_index, impact_factor, etc.)
    """
    # Clean ID
    clean_id = source_id.split('/')[-1]
    url = f"https://api.openalex.org/sources/{clean_id}"
    
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            summary = data.get("summary_stats", {})
            return {
                "h_index": summary.get("h_index", 0),
                "i10_index": summary.get("i10_index", 0),
                "works_count": data.get("works_count", 0),
                "cited_by_count": data.get("cited_by_count", 0),
                "2yr_mean_citedness": summary.get("2yr_mean_citedness", 0)
            }
        return {}
    except Exception as e:
        print(f"   [OpenAlex] ⚠️ Error fetching journal metrics: {e}")
        return {}


def detect_international_collab(openalex_data: Dict) -> bool:
    """
    Detect if publication has international collaboration.
    
    Args:
        openalex_data: OpenAlex publication data
    
    Returns:
        True if authors from multiple countries
    
    Example:
        >>> data = {"authorships": [...]}
        >>> detect_international_collab(data)
        True
    """
    authorships = openalex_data.get("authorships", [])
    countries = set()
    
    for authorship in authorships:
        institutions = authorship.get("institutions", [])
        for institution in institutions:
            country = institution.get("country_code")
            if country:
                countries.add(country)
    
    # International if more than one country
    is_international = len(countries) > 1
    
    if is_international:
        print(f"   [OpenAlex] 🌍 International collaboration: {countries}")
    
    return is_international


def extract_journal_info(openalex_data: Dict) -> Dict[str, any]:
    """
    Extract journal information from OpenAlex data.
    
    Args:
        openalex_data: OpenAlex publication data
    
    Returns:
        Dictionary with journal info (name, issn, type, OA status)
    """
    primary_location = openalex_data.get("primary_location", {})
    source = primary_location.get("source", {}) if primary_location else {}
    
    return {
        "journal_name": source.get("display_name"),
        "issn": source.get("issn_l"),
        "source_id": source.get("id"),  # Added ID for fetching metrics

        "journal_type": source.get("type"),
        "is_oa": primary_location.get("is_oa", False) if primary_location else False,
        "oa_status": openalex_data.get("open_access", {}).get("oa_status")
    }


def get_openalex_id(openalex_data: Dict) -> str:
    """
    Extract OpenAlex ID from publication data.
    
    Args:
        openalex_data: OpenAlex publication data
    
    Returns:
        OpenAlex ID (e.g., "W1234567890")
    """
    openalex_id = openalex_data.get("id", "")
    
    
    if openalex_id.startswith("https://openalex.org/"):
        # Extract ID from URL
        return openalex_id.split("/")[-1]
    
    return openalex_id


def extract_publication_metadata(data: Dict) -> Dict:
    """
    Extract relevant metrics and metadata from OpenAlex response.
    
    Args:
        data: Raw dictionary from OpenAlex API
        
    Returns:
        Dictionary with structured metrics for DB storage, or None if data is invalid
    """
    if not data:
        print("   [OpenAlex] ❌ extract_publication_metadata received None data")
        return None
    
    # Debug: Log what we received
    print(f"   [OpenAlex] Extracting metadata from response with keys: {list(data.keys())[:10]}")
        
    primary_location = data.get("primary_location") or {}
    source = primary_location.get("source") or {}
    open_access = data.get("open_access") or {}
    primary_topic = data.get("primary_topic") or {}
    
    result = {
        "title": data.get("title"),  # Added title extraction
        "cited_by_count": data.get("cited_by_count", 0),
        "publication_year": data.get("publication_year"),
        "journal_name": source.get("display_name"),
        "issn": source.get("issn_l"),
        "language": data.get("language"),
        "openalex_id": data.get("id"),
        "is_oa": primary_location.get("is_oa", False),
        "oa_status": open_access.get("oa_status"),
        "topic": primary_topic.get("display_name"),
        "journal_metrics": None
    }
    
    # Fetch Journal H-Index if Source ID is present
    source_id = source.get("id")
    if source_id:
        print(f"   [OpenAlex] Fetching metrics for source: {source_id}")
        j_metrics = fetch_journal_metrics(source_id)
        if j_metrics:
            result["journal_metrics"] = j_metrics
            # Also flatten h_index for easier access if needed
            print(f"   [OpenAlex] ✅ Journal H-Index: {j_metrics.get('h_index')}")

    
    # Debug: Log what we extracted
    print(f"   [OpenAlex] Extracted - Title: {result['title'][:50] if result['title'] else 'None'}, Year: {result['publication_year']}, Journal: {result['journal_name']}")
    
    return result


def search_venue_by_name(name: str) -> Dict:
    """
    Search for a venue/journal by name in OpenAlex to get details (publisher, ISSN).
    
    Args:
        name: Journal/Venue name
        
    Returns:
        Dictionary with venue details or None
    """
    if not name or len(name) < 3:
        return None
        
    clean_name = urllib.parse.quote(name)
    url = f"https://api.openalex.org/sources?filter=display_name.search:{clean_name}&per_page=1"
    
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        print(f"   [OpenAlex] Searching venue details for: {name}...")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                match = results[0]
                publisher = match.get("host_organization_name", "Unknown")
                issn = match.get("issn_l")
                print(f"   [OpenAlex] ✅ Found venue: {match.get('display_name')} (Publisher: {publisher})")
                
                return {
                    "id": match.get("id"),
                    "display_name": match.get("display_name"),
                    "publisher": publisher,
                    "issn": issn,
                    "type": match.get("type")
                }
    except Exception as e:
        print(f"   [OpenAlex] ⚠️ Venue search failed: {e}")
    
    return None
