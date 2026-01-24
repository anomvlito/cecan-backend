"""
Experimental DOI Extraction Service
====================================
⚠️ EXPERIMENTAL CODE - DO NOT USE IN PRODUCTION ⚠️

This service implements aggressive DOI extraction strategies
for problematic PDFs (interleaved text, missing headers, etc.).

Created for debugging and testing purposes.
Safe to delete without affecting production flow.
"""

import io
import re
import requests
from typing import Optional, Dict, List, Tuple
import pdfplumber
import PyPDF2

from config import OPENALEX_CONTACT_EMAIL


def clean_interleaved_text(text: str) -> str:
    """
    Heuristic cleanup for "letter soup" (interleaved text).

    Example: "hDttOpsI://" might be "https://" with noise
    Strategy: Try to extract even-positioned and odd-positioned characters

    Args:
        text: Raw text snippet that might be interleaved

    Returns:
        Cleaned text (best effort)
    """
    if not text or len(text) < 10:
        return text

    # Strategy 1: Extract every other character (even positions)
    even_chars = ''.join([text[i] for i in range(0, len(text), 2)])

    # Strategy 2: Extract every other character (odd positions)
    odd_chars = ''.join([text[i] for i in range(1, len(text), 2)])

    # Check if either pattern looks like a DOI
    doi_pattern = r'10\.\d{4}/[-._;()/:a-zA-Z0-9]+'

    if re.search(doi_pattern, even_chars):
        return even_chars
    if re.search(doi_pattern, odd_chars):
        return odd_chars

    # No clear pattern found, return original
    return text


def extract_text_aggressive(file_bytes: bytes) -> Dict[str, str]:
    """
    Extract text using MULTIPLE strategies to handle broken PDFs.

    Returns:
        Dictionary with keys:
        - 'layout_true': Text extracted with layout=True (standard)
        - 'layout_false': Text extracted with layout=False (stream order)
        - 'pypdf2': Text extracted with PyPDF2
    """
    results = {
        'layout_true': '',
        'layout_false': '',
        'pypdf2': ''
    }

    # Strategy 1: pdfplumber with layout=True (standard, preserves visual layout)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text(layout=True)
                if page_text:
                    text_parts.append(page_text)
            results['layout_true'] = "\n\n".join(text_parts)
    except Exception as e:
        print(f"[Experimental] layout=True failed: {e}")

    # Strategy 2: pdfplumber with layout=False (stream order, might fix interleaving)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text(layout=False)
                if page_text:
                    text_parts.append(page_text)
            results['layout_false'] = "\n\n".join(text_parts)
    except Exception as e:
        print(f"[Experimental] layout=False failed: {e}")

    # Strategy 3: PyPDF2 as fallback
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        results['pypdf2'] = "\n\n".join(text_parts)
    except Exception as e:
        print(f"[Experimental] PyPDF2 failed: {e}")

    return results


def extract_doi_dual_search(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Search for DOI in BOTH header AND footer of document.

    Args:
        text: Full document text

    Returns:
        Tuple of (doi, method, raw_snippet) or None
        - doi: Cleaned DOI string
        - method: Where/how it was found
        - raw_snippet: Raw text snippet where DOI was found (for debugging)
    """
    # Normalize text
    normalized_text = ' '.join(text.split())
    normalized_text = normalized_text.replace('\u2013', '-').replace('\u2014', '-')

    # DOI regex patterns (same as production)
    patterns = [
        (r'(?:https?://)?(?:dx\.)?doi\.org/(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', 'url_pattern'),
        (r'DOI\s*:?\s*(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', 'doi_prefix'),
        (r'\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', 'standard_pattern'),
    ]

    # DUAL SEARCH STRATEGY
    searches = [
        ('header', normalized_text[:3000]),
        ('footer', normalized_text[-3000:]),
    ]

    for location, text_chunk in searches:
        for pattern, pattern_name in patterns:
            match = re.search(pattern, text_chunk, re.IGNORECASE)
            if match:
                doi = match.group(1).rstrip('.,;)]')

                # Extract a snippet around the match for debugging
                start = max(0, match.start() - 50)
                end = min(len(text_chunk), match.end() + 50)
                snippet = text_chunk[start:end]

                method = f"{location}_{pattern_name}"
                return doi, method, snippet

    return None


def extract_doi_with_heuristics(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Try to extract DOI with heuristic cleanup for interleaved text.

    Args:
        text: Raw text that might be corrupted

    Returns:
        Tuple of (doi, method, snippet) or None
    """
    # First try standard dual search
    result = extract_doi_dual_search(text)
    if result:
        return result

    # If that fails, try cleaning interleaved text
    # Look for suspicious patterns that might be DOIs with noise
    suspicious_patterns = [
        r'[hH].*[tT].*[pP].*[sS].*:.*/.*/.*doi',  # Interleaved "https://doi"
        r'd.*o.*i.*:?\s*1.*0\.\d',  # Interleaved "doi: 10."
    ]

    for pattern in suspicious_patterns:
        match = re.search(pattern, text[:5000])
        if match:
            # Found suspicious text, try cleaning it
            suspicious_text = match.group(0)
            cleaned = clean_interleaved_text(suspicious_text)

            # Try standard DOI extraction on cleaned text
            doi_result = extract_doi_dual_search(cleaned)
            if doi_result:
                doi, _, snippet = doi_result
                return doi, 'heuristic_deinterleave', f"Original: {suspicious_text[:100]} | Cleaned: {cleaned[:100]}"

    return None


def validate_doi_with_openalex(doi: str) -> Optional[Dict]:
    """
    Validate a DOI by querying OpenAlex API.

    Args:
        doi: DOI string (e.g., "10.1234/abc")

    Returns:
        Dictionary with OpenAlex metadata if found, None otherwise
        Keys: title, year, journal, authors, doi_url
    """
    # Build OpenAlex works API URL
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"

    # Use polite pool for faster access
    headers = {
        "User-Agent": f"mailto:{OPENALEX_CONTACT_EMAIL}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            return None  # DOI doesn't exist

        if response.status_code != 200:
            print(f"[Experimental] OpenAlex returned {response.status_code}")
            return None

        data = response.json()

        # Extract key metadata
        authors = []
        for authorship in data.get('authorships', [])[:5]:  # First 5 authors
            author = authorship.get('author', {})
            if author.get('display_name'):
                authors.append(author['display_name'])

        journal_name = None
        primary_location = data.get('primary_location')
        if primary_location:
            source = primary_location.get('source')
            if source:
                journal_name = source.get('display_name')

        return {
            'title': data.get('title', 'N/A'),
            'year': data.get('publication_year'),
            'journal': journal_name,
            'authors': authors,
            'doi_url': data.get('doi', f"https://doi.org/{doi}"),
            'cited_by_count': data.get('cited_by_count', 0),
            'type': data.get('type', 'N/A')
        }

    except requests.Timeout:
        print("[Experimental] OpenAlex timeout")
        return None
    except Exception as e:
        print(f"[Experimental] OpenAlex error: {e}")
        return None


def experimental_extract_and_validate(file_bytes: bytes, filename: str) -> Dict:
    """
    Main experimental pipeline: Extract DOI aggressively and validate with OpenAlex.

    Args:
        file_bytes: PDF file as bytes
        filename: Original filename (for logging)

    Returns:
        Rich dictionary with:
        - doi_found: DOI string or None
        - extraction_method: How it was found
        - raw_text_snippet: Text where DOI was found (debugging)
        - openalex_metadata: Metadata from OpenAlex (if valid)
        - all_extractions: Results from all extraction strategies
        - success: Boolean indicating if DOI was found AND validated
    """
    print(f"\n{'='*60}")
    print(f"🔬 EXPERIMENTAL EXTRACTION: {filename}")
    print(f"{'='*60}\n")

    # Step 1: Extract text with all strategies
    print("📄 Extracting text with multiple strategies...")
    text_results = extract_text_aggressive(file_bytes)

    all_extractions = {}
    for strategy, text in text_results.items():
        if text:
            all_extractions[strategy] = {
                'text_length': len(text),
                'first_500_chars': text[:500],
                'last_500_chars': text[-500:] if len(text) > 500 else text
            }

    # Step 2: Try to find DOI in each extraction
    print("\n🔍 Searching for DOI patterns...")
    doi_candidates = []

    for strategy, text in text_results.items():
        if not text:
            continue

        # Try standard + heuristic extraction
        result = extract_doi_with_heuristics(text)
        if result:
            doi, method, snippet = result
            doi_candidates.append({
                'doi': doi,
                'extraction_strategy': strategy,
                'method': method,
                'snippet': snippet
            })
            print(f"   ✓ Found in '{strategy}' via '{method}': {doi}")

    # Step 3: If we have candidates, validate with OpenAlex
    best_result = {
        'doi_found': None,
        'extraction_method': None,
        'raw_text_snippet': None,
        'openalex_metadata': None,
        'all_extractions': all_extractions,
        'all_candidates': doi_candidates,
        'success': False
    }

    if doi_candidates:
        print(f"\n✅ Found {len(doi_candidates)} DOI candidate(s). Validating with OpenAlex...")

        for candidate in doi_candidates:
            doi = candidate['doi']
            print(f"\n   🌐 Validating: {doi}")

            metadata = validate_doi_with_openalex(doi)
            if metadata:
                print(f"   ✅ VALID! Paper: {metadata['title'][:80]}...")
                best_result = {
                    'doi_found': doi,
                    'extraction_method': f"{candidate['extraction_strategy']} + {candidate['method']}",
                    'raw_text_snippet': candidate['snippet'],
                    'openalex_metadata': metadata,
                    'all_extractions': all_extractions,
                    'all_candidates': doi_candidates,
                    'success': True
                }
                break  # Stop at first valid DOI
            else:
                print(f"   ❌ Invalid or not found in OpenAlex")
    else:
        print("\n❌ No DOI candidates found in any extraction strategy")

    print(f"\n{'='*60}\n")
    return best_result
