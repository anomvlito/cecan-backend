"""
OpenAlex Publication Search Service
Atomic service for searching publications by title when DOI is not available
"""

import re
import requests
from typing import Dict, List, Optional
from difflib import SequenceMatcher

from config import OPENALEX_CONTACT_EMAIL


def clean_publication_title(title: str) -> str:
    """
    Clean publication title by removing common prefixes, numbers, and special characters.
    
    Args:
        title: Raw publication title (may have "01-", "Paper_", etc.)
        
    Returns:
        Cleaned title suitable for search
        
    Examples:
        >>> clean_publication_title("01- Alpha-Lipoic Acid Study (2024)")
        "Alpha-Lipoic Acid Study"
        >>> clean_publication_title("63- Beyond the Pandemic PPérez (2025)")
        "Beyond the Pandemic"
    """
    # Remove leading numbers and separators (01-, 63-, etc.)
    title = re.sub(r'^\d+[-_.\s]+', '', title)
    
    # Remove file extensions
    title = re.sub(r'\.(pdf|PDF)$', '', title)
    
    # Remove trailing parentheses with years or author initials
    # Match patterns like "(2024)", "(PPérez 2025)", "PPérez (2025)"
    title = re.sub(r'\s+[A-Z][A-Za-zé]+\s*\(\d{4}\)$', '', title)
    title = re.sub(r'\s+\(\d{4}\)$', '', title)
    title = re.sub(r'\s+\([^)]*\d{4}[^)]*\)$', '', title)
    
    # Replace underscores with spaces
    title = title.replace('_', ' ')
    
    # Remove extra whitespace
    title = ' '.join(title.split())
    
    return title.strip()


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity score between two titles (0-1 scale).
    
    Args:
        title1: First title
        title2: Second title
        
    Returns:
        Similarity score from 0.0 (no match) to 1.0 (perfect match)
    """
    # Normalize both titles
    t1 = title1.lower().strip()
    t2 = title2.lower().strip()
    
    # Use SequenceMatcher for fuzzy matching
    return SequenceMatcher(None, t1, t2).ratio()


def search_publications_by_title(
    title: str, 
    limit: int = 5,
    min_score: float = 0.5
) -> List[Dict]:
    """
    Search OpenAlex for publications matching a title.
    
    Args:
        title: Publication title to search for
        limit: Maximum number of results to return
        min_score: Minimum similarity score to include (0-1)
        
    Returns:
        List of candidate publications with metadata and similarity scores
        
    Example:
        >>> results = search_publications_by_title("Alpha-Lipoic Acid Study")
        >>> results[0]['similarity_score']
        0.92
    """
    cleaned_title = clean_publication_title(title)
    
    # Build OpenAlex search URL
    # Use title.search parameter for fuzzy matching
    url = "https://api.openalex.org/works"
    params = {
        "search": cleaned_title,
        "per_page": limit * 2,  # Get more results to filter by similarity
        "sort": "relevance_score:desc"
    }
    
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }
    
    try:
        print(f"   [OpenAlex Search] Searching for: '{cleaned_title}'")
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"   [OpenAlex Search] ❌ API error {response.status_code}")
            return []
        
        data = response.json()
        results = data.get("results", [])
        
        print(f"   [OpenAlex Search] Found {len(results)} raw results")
        
        # Calculate similarity scores and filter
        candidates = []
        for work in results:
            work_title = work.get("title", "")
            if not work_title:
                continue
            
            similarity = calculate_title_similarity(cleaned_title, work_title)
            
            # Only include if above minimum score
            if similarity < min_score:
                continue
            
            # Extract relevant data
            primary_location = work.get("primary_location") or {}
            source = primary_location.get("source") or {}
            
            candidate = {
                "openalex_id": work.get("id", "").split("/")[-1],
                "title": work_title,
                "publication_year": work.get("publication_year"),
                "journal_name": source.get("display_name"),
                "doi": work.get("doi", "").replace("https://doi.org/", "") if work.get("doi") else None,
                "cited_by_count": work.get("cited_by_count", 0),
                "is_oa": primary_location.get("is_oa", False),
                "similarity_score": round(similarity, 3),
                "raw_data": work  # Store full response for later sync
            }
            
            candidates.append(candidate)
        
        # Sort by similarity score
        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # Return top N results
        top_results = candidates[:limit]
        
        print(f"   [OpenAlex Search] Returning {len(top_results)} candidates (min_score={min_score})")
        for i, c in enumerate(top_results, 1):
            print(f"      {i}. [{c['similarity_score']:.2f}] {c['title'][:60]}")
        
        return top_results
    
    except requests.exceptions.Timeout:
        print("   [OpenAlex Search] ⚠️ Request timeout")
        return []
    except Exception as e:
        print(f"   [OpenAlex Search] ❌ Error: {str(e)}")
        return []


def link_publication_to_openalex(publication_id: int, openalex_data: Dict, db) -> bool:
    """
    Link a publication to OpenAlex data and sync all metadata.
    
    Args:
        publication_id: Database ID of the publication
        openalex_data: Full OpenAlex work data (from candidate's raw_data)
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    from core.models import Publication
    from services.openalex_service import extract_publication_metadata
    from datetime import datetime
    
    try:
        pub = db.query(Publication).filter(Publication.id == publication_id).first()
        if not pub:
            print(f"   [Link] ❌ Publication {publication_id} not found")
            return False
        
        # Extract metadata
        metadata = extract_publication_metadata(openalex_data)
        if not metadata:
            print(f"   [Link] ❌ Could not extract metadata from OpenAlex data")
            return False
        
        # Update publication
        pub.title = metadata.get("title") or pub.title
        pub.year = str(metadata.get("publication_year")) if metadata.get("publication_year") else pub.year
        pub.canonical_doi = openalex_data.get("doi", "").replace("https://doi.org/", "") if openalex_data.get("doi") else pub.canonical_doi
        pub.doi_verification_status = "valid_openalex"
        pub.metrics_data = metadata
        pub.metrics_last_updated = datetime.utcnow()
        
        db.commit()
        
        print(f"   [Link] ✅ Successfully linked publication {publication_id} to OpenAlex")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"   [Link] ❌ Error linking publication: {str(e)}")
        return False
