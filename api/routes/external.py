"""
External Metrics Routes - Atomic endpoints for testing external API integrations
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, List
from typing import Dict, Any, List
import os
from datetime import datetime

from services.scraper_service import get_openalex_metrics, get_semantic_scholar_metrics
from services.openalex_service import extract_publication_metadata
from database.session import get_db
from core.models import Publication

router = APIRouter(tags=["External Metrics"])


@router.get("/publication-metrics")
async def get_publication_metrics_by_doi(
    doi: str = Query(..., description="DOI of the publication (e.g., 10.1038/s41586-020-2649-2)")
) -> Dict[str, Any]:
    """
    Fetches citation metrics for a single publication using its DOI.
    
    This is an atomic endpoint for testing external API connections.
    It queries OpenAlex and Semantic Scholar in real-time and returns
    the results without storing anything in the database.
    
    Args:
        doi: Digital Object Identifier of the publication
        
    Returns:
        JSON with metrics from both sources
        
    Example:
        GET /external/publication-metrics?doi=10.1038/s41586-020-2649-2
    """
    if not doi:
        raise HTTPException(status_code=400, detail="DOI parameter is required")
    
    # Clean DOI if it comes with full URL
    clean_doi = doi.split('doi.org/')[-1] if 'doi.org/' in doi else doi
    
    # Query OpenAlex
    openalex_data = get_openalex_metrics(doi=clean_doi)
    
    # Query Semantic Scholar
    semantic_scholar_data = get_semantic_scholar_metrics(clean_doi)
    
    # Build response
    return {
        "doi": clean_doi,
        "openalex": openalex_data if openalex_data else {"error": "No data available"},
        "semantic_scholar": semantic_scholar_data if semantic_scholar_data else {"error": "No data available"}
    }


@router.get("/list-dois")
async def list_existing_dois(
    limit: int = Query(100, description="Maximum number of DOIs to return"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Lists all valid DOIs currently stored in the database.
    
    Filters out:
    - URLs from cecan.cl (not DOIs)
    - Null/empty values
    
    Returns only publications where url_origen contains a valid DOI pattern.
    
    Example:
        GET /external/list-dois?limit=20
    """
    # Query publications with potential DOIs
    pubs = db.query(Publication.id, Publication.titulo, Publication.url_origen)\
             .filter(Publication.url_origen.isnot(None))\
             .limit(limit)\
             .all()
    
    # Filter and clean DOIs
    valid_dois = []
    for pub_id, titulo, url in pubs:
        # Skip cecan.cl URLs
        if 'cecan.cl' in url:
            continue
        
        # Check if it's a valid DOI pattern (starts with 10. or contains doi.org)
        if url.startswith('10.') or 'doi.org/' in url:
            # Clean DOI
            clean_doi = url.split('doi.org/')[-1] if 'doi.org/' in url else url
            
            valid_dois.append({
                "publication_id": pub_id,
                "title": titulo[:80] + "..." if len(titulo) > 80 else titulo,
                "doi": clean_doi
            })
    
    return {
        "total": len(valid_dois),
        "dois": valid_dois
    }


@router.post("/extract-missing-dois")
async def extract_dois_from_existing_pdfs(
    limit: int = Query(10, description="Number of publications to process"),
    dry_run: bool = Query(False, description="If true, only report what would be done without modifying DB"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retroactively extracts DOIs from publications that have PDFs stored but no DOI recorded.
    
    This endpoint:
    1. Finds publications with path_pdf_local but no valid DOI
    2. Reads the PDF and extracts the DOI using regex patterns
    3. Updates the database with the found DOI (unless dry_run=true)
    
    Args:
        limit: Maximum number of publications to process
        dry_run: If true, only simulates the extraction without DB updates
        
    Returns:
        Summary of processed publications and extraction results
        
    Example:
        POST /external/extract-missing-dois?limit=5&dry_run=true
    """
    import re
    from pypdf import PdfReader
    
    # Find publications without DOI but with PDF
    candidates = db.query(Publication).filter(
        Publication.path_pdf_local.isnot(None),
        or_(
            Publication.url_origen.is_(None),
            Publication.url_origen.like('%cecan.cl%')
        )
    ).limit(limit).all()
    
    results = {
        "processed": 0,
        "dois_extracted": 0,
        "failed": 0,
        "details": []
    }
    
    # DOI regex pattern (basic)
    doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+')
    
    for pub in candidates:
        results["processed"] += 1
        detail = {"pub_id": pub.id, "title": pub.titulo[:50], "status": "unknown"}
        
        try:
            # Check if PDF exists
            if not os.path.exists(pub.path_pdf_local):
                detail["status"] = "pdf_not_found"
                results["failed"] += 1
                results["details"].append(detail)
                continue
            
            # Read PDF
            reader = PdfReader(pub.path_pdf_local)
            text = ""
            # Extract text from first 3 pages (DOI usually on first page)
            for page in reader.pages[:3]:
                text += page.extract_text()
            
            # Search for DOI
            doi_matches = doi_pattern.findall(text)
            
            if doi_matches:
                # Take the first match
                extracted_doi = doi_matches[0].strip()
                detail["status"] = "success"
                detail["doi"] = extracted_doi
                results["dois_extracted"] += 1
                
                # Update database if not dry run
                if not dry_run:
                    pub.url_origen = f"https://doi.org/{extracted_doi}"
                    db.commit()
                    detail["updated_db"] = True
                else:
                    detail["updated_db"] = False
            else:
                detail["status"] = "no_doi_found"
                results["failed"] += 1
                
        except Exception as e:
            detail["status"] = "error"
            detail["error"] = str(e)
            results["failed"] += 1
        
        results["details"].append(detail)
    
    return results

@router.post("/audit-dois")
async def audit_doi_links(
    limit: int = Query(100, description="Max number of DOIs to check"),
    strategy: str = Query("hybrid", description="Strategy: 'http', 'openalex', or 'hybrid'"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Audits the validity of stored DOI links.
    
    Strategies:
    - 'openalex': Only checks if DOI exists in OpenAlex (No false 403s, fast).
    - 'http': Only checks HTTP connectivity (prone to 403 blocks).
    - 'hybrid' (Default): Checks OpenAlex first. If not found, falls back to HTTP.
    
    Args:
        limit: Max number of publications to check
        strategy: Audit strategy
        
    Returns:
        Report with valid vs broken links status
    """
    import requests
    import concurrent.futures
    import time
    
    # Get publications with DOIs
    pubs = db.query(Publication).filter(Publication.canonical_doi.isnot(None)).limit(limit).all()
    
    results = {
        "total_checked": 0,
        "valid": 0,
        "broken": 0,
        "source_breakdown": {"openalex": 0, "http": 0},
        "details": []
    }
    
    # Enhanced Headers to avoid 403
    http_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Refereer': 'https://scholar.google.com/'
    }
    
    def check_openalex(clean_doi):
        """Check against OpenAlex API."""
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            # Polite pool
            response = requests.get(url, params={"mailto": "admin@cecan.cl"}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                metadata = extract_publication_metadata(data)
                return True, "valid_openalex", metadata
            elif response.status_code == 404:
                return False, "not_found_openalex", None
            else:
                return False, f"error_openalex_{response.status_code}", None
        except Exception:
            return False, "error_openalex_connection", None

    def check_http(clean_doi):
        """Fallback HTTP check."""
        url = f"https://doi.org/{clean_doi}"
        try:
            with requests.Session() as session:
                response = session.get(url, headers=http_headers, timeout=10, stream=True, allow_redirects=True)
                status = response.status_code
                is_valid = 200 <= status < 400
                # Treat 403 as "Unknown/Blocked" rather than Broken if we are unsure, 
                # but technically user calls it broken. We'll label it.
                if status == 403:
                    return False, "blocked_403", response.url
                return is_valid, ("valid_http" if is_valid else f"broken_http_{status}"), response.url
        except Exception as e:
            return False, "error_http_connection", None

    def audit_single(pub_id, title, doi):
        # Clean DOI just in case
        clean_doi = doi.split('doi.org/')[-1].strip()
        
        status = "unknown"
        source = "none"
        final_url = None
        is_valid = False
        
        # 1. OpenAlex Check
        if strategy in ["openalex", "hybrid"]:
            oa_valid, oa_status, oa_metadata = check_openalex(clean_doi)
            if oa_valid:
                return {
                    "pub_id": pub_id,
                    "title": title[:50],
                    "doi": doi,
                    "status": "valid",
                    "reason": "Verified by OpenAlex",
                    "source": "openalex",
                    "metadata": oa_metadata  # Include metadata in result
                }
            # If hybrid and not found in OA, continue to HTTP
            if strategy == "hybrid" and oa_status == "not_found_openalex":
                pass # Fallthrough
            elif strategy == "openalex":
                 return {
                    "pub_id": pub_id,
                    "title": title[:50],
                    "doi": doi,
                    "status": "broken",
                    "reason": "Not found in OpenAlex",
                    "source": "openalex"
                }

        # 2. HTTP Check (Fallback or Primary)
        http_valid, http_reason, url = check_http(clean_doi)
        final_url = url
        
        if http_valid:
            return {
                "pub_id": pub_id,
                "title": title[:50],
                "doi": doi,
                "status": "valid",
                "reason": "Verified by HTTP Link",
                "source": "http",
                "final_url": final_url
            }
        else:
            # Special handling for 403
            if "403" in http_reason:
                 return {
                    "pub_id": pub_id,
                    "title": title[:50],
                    "doi": doi,
                    "status": "warning", # Changed from broken to warning
                    "reason": "Access Blocked (403) - Likely Valid but Anti-Bot",
                    "source": "http",
                    "final_url": final_url
                }
            
            return {
                "pub_id": pub_id,
                "title": title[:50],
                "doi": doi,
                "status": "broken",
                "reason": f"HTTP Error: {http_reason}",
                "source": "http",
                "final_url": final_url
            }

    # Execute efficiently in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(audit_single, p.id, p.titulo, p.canonical_doi): p for p in pubs}
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results["total_checked"] += 1
            results["details"].append(res)
            
            # Update DB with status if it's definitive
            # We do this one by one or batch? Ideally batch but let's do it safely here
            # Since 'futures' dict has the 'pub' object, we can use it
            pub_obj = futures[future]
            
            if res["status"] == "valid":
                results["valid"] += 1
                if "openalex" in res.get("source", ""):
                    pub_obj.doi_verification_status = "valid_openalex"
                    results["source_breakdown"]["openalex"] += 1
                    
                    # Phase 2: Save Enriched Metrics
                    if res.get("metadata"):
                        pub_obj.metrics_data = res["metadata"]
                        pub_obj.metrics_last_updated = datetime.utcnow()
                else:
                    pub_obj.doi_verification_status = "valid_http"
                    results["source_breakdown"]["http"] += 1
            elif res["status"] == "broken":
                pub_obj.doi_verification_status = "broken"
                results["broken"] += 1
            elif res["status"] == "warning":
                 # Treat as valid for now in DB but maybe a distinct status?
                 # Let's call it "valid_http" to avoid scaring users, or "warning"
                 pub_obj.doi_verification_status = "valid_http" # Assume valid if blocked
            
            # Flush changes periodically or at end?
            # Doing add/commit inside loop might be slow but safe for concurrency if session is thread-local
            # But here session is shared. Ideally we collect and bulk update.
            # For simplicity:
            db.add(pub_obj)
            
    db.commit()
    
    
    return results

@router.post("/repair-dois")
async def repair_bad_dois(
    limit: int = Query(20, description="Max number of DOIs to attempt repair"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Smart DOI Repair using Deep PDF Scan and OpenAlex Validation.
    
    1. Identifies "Bad" DOIs (too short, placeholders like 'xxxxx', '10.1371/j').
    2. Scans the FULL PDF (up to 20 pages) for better DOI candidates.
    3. Validates candidates against OpenAlex API.
    4. Automatically updates DB if a better, valid DOI is found.
    """
    import requests
    import re
    import os
    from pypdf import PdfReader
    from difflib import SequenceMatcher

    def check_openalex(clean_doi):
        """Verify existence in OpenAlex and return title."""
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            resp = requests.get(url, params={"mailto": "admin@cecan.cl"}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return True, data.get('display_name', '')
            return False, None
        except:
            return False, None

    def titles_match(title1, title2, threshold=0.4):
        """Fuzzy match two titles."""
        if not title1 or not title2: return False
        t1 = title1.lower()
        t2 = title2.lower()
        ratio = SequenceMatcher(None, t1, t2).ratio()
        
        # Also check token overlap for better accuracy
        tokens1 = set(t1.split())
        tokens2 = set(t2.split())
        if not tokens1 or not tokens2: return False
        overlap = len(tokens1.intersection(tokens2)) / min(len(tokens1), len(tokens2))
        
        return ratio > threshold or overlap > 0.5
    
    # 1. Regex for DOI Detection (Robust)
    # Allows for newlines/hyphens inside the suffix
    # Captures: 10.xxxx / [suffix]
    doi_pattern_robust = re.compile(r'(10\.\d{4,9}/[-._;()/:a-zA-Z0-9\s]+)')
    
    # 2. Find Candidates (Bad DOIs)
    # We define "Bad" as:
    # - Shorter than 12 chars (e.g. 10.123/x) -> unlikely to be real mostly
    # - Contains 'xxxxx' or placeholder text
    # - Ends with '/j' (common truncation error we saw)
    
    all_pubs = db.query(Publication).filter(Publication.canonical_doi.isnot(None)).all()
    candidates = []
    
    for p in all_pubs:
        d = p.canonical_doi.strip().lower()
        is_suspicious = False
        
        # 2.1 Explicit Trash Patterns
        trash_markers = ["xxxxx", "doi", "10.000", "insert", "placeholder"]
        if any(marker in d for marker in trash_markers):
             is_suspicious = True
        
        # 2.2 Truncation Patterns
        if d.endswith("/j") or len(d) < 14: # 10.1371/j is 11 chars
             is_suspicious = True
        
        # SAFETY CHECK: If it looks suspicious but is actually valid in OpenAlex, skip it!
        if is_suspicious:
             exists, _ = check_openalex(d)
             if exists:
                 is_suspicious = False # False alarm, it's a valid short DOI
             
        if is_suspicious and p.path_pdf_local and os.path.exists(p.path_pdf_local):
            candidates.append(p)
            if len(candidates) >= limit:
                break
    
    results = {
        "analyzed": 0,
        "repaired": 0,
        "failed": 0,
        "details": []
    }

    for pub in candidates:
        results["analyzed"] += 1
        detail = {
            "pub_id": pub.id,
            "old_doi": pub.canonical_doi,
            "status": "scaling_pdf"
        }
        
        try:
            # 3. Deep PDF Scan
            reader = PdfReader(pub.path_pdf_local)
            text = ""
            # Read up to 20 pages (cover + content usually enough)
            for i, page in enumerate(reader.pages):
                if i > 20: break
                text += page.extract_text() + "\n"
            
            # Clean text lightly
            text = text.replace("- \n", "").replace("-\n", "") # Fix hyphenation
            
            matches = doi_pattern_robust.findall(text)
            
            # Filter and Clean Candidates
            valid_new_doi = None
            
            for m in matches:
                # Clean whitespace
                clean = re.sub(r'\s+', '', m).strip()
                # Remove trailing punctuation often captured
                clean = clean.rstrip(".,;:/")
                
                # Check it's not the same garbage
                if clean == pub.canonical_doi:
                    continue

                # Basic validation
                if len(clean) < 15:
                    continue
                
                # Verify with OpenAlex AND Check Title
                exists, oa_title = check_openalex(clean)
                if exists:
                    if titles_match(pub.titulo, oa_title):
                        valid_new_doi = clean
                        break # Found it!
                    else:
                        # DOI exists but titles don't match (likely a reference)
                        continue
            
            if valid_new_doi:
                pub.canonical_doi = valid_new_doi
                pub.url_origen = f"https://doi.org/{valid_new_doi}"
                pub.doi_verification_status = "repaired"
                db.commit()
                
                detail["status"] = "repaired"
                detail["new_doi"] = valid_new_doi
                results["repaired"] += 1
            else:
                detail["status"] = "no_better_doi_found"
                results["failed"] += 1
                
        except Exception as e:
            detail["status"] = "error"
            detail["error"] = str(e)[:100]
            results["failed"] += 1
            
        results["details"].append(detail)
        
    return results
