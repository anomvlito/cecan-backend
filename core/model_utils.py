"""
Helper utilities for Publication model
"""

def compute_has_doi(canonical_doi: str = None, url: str = None) -> bool:
    """
    Compute whether a publication has a DOI based on canonical_doi or url.
    
    Args:
        canonical_doi: The normalized DOI string
        url: The publication URL
        
    Returns:
        True if DOI is present, False otherwise
        
    Examples:
        >>> compute_has_doi("10.1234/example", None)
        True
        >>> compute_has_doi(None, "https://doi.org/10.1234/example")
        True
        >>> compute_has_doi(None, "https://example.com")
        False
    """
    if canonical_doi:
        return True
    
    if url:
        return "10." in url or "doi.org" in url
    
    return False
