"""
ORCID Metadata Service
Queries ORCID API to extract author names, countries, and affiliations
"""

import requests
import time
import re
from typing import Dict, List, Set, Optional
from datetime import datetime
import PyPDF2

# ORCID API Configuration
ORCID_API_BASE = "https://pub.orcid.org/v3.0"
ORCID_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "CECAN-Platform/1.0"
}

# Rate limiting
REQUESTS_PER_SECOND = 1
LAST_REQUEST_TIME = 0


def get_orcid_metadata(orcid: str) -> Optional[Dict]:
    """
    Query ORCID public API to get author metadata.
    
    Args:
        orcid: ORCID identifier (e.g., "0000-0002-1234-5678")
        
    Returns:
        Dict with author metadata or None if error
        {
            "name": "Full Name",
            "given_name": "First",
            "family_name": "Last",
            "countries": ["Chile", "USA"],
            "institutions": [{"name": "...", "country": "..."}],
            "last_updated": "2026-01-05T..."
        }
    """
    global LAST_REQUEST_TIME
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - LAST_REQUEST_TIME
    if time_since_last < (1.0 / REQUESTS_PER_SECOND):
        time.sleep((1.0 / REQUESTS_PER_SECOND) - time_since_last)
    
    try:
        url = f"{ORCID_API_BASE}/{orcid}/record"  # Changed from /person to /record to get everything
        response = requests.get(url, headers=ORCID_HEADERS, timeout=10)
        LAST_REQUEST_TIME = time.time()
        
        if response.status_code != 200:
            print(f"   ⚠️  ORCID API error {response.status_code} for {orcid}")
            return None
        
        data = response.json()
        
        # Extract name (nested in person)
        person = data.get("person", {})
        name_data = person.get("name", {})
        given_names = name_data.get("given-names", {}).get("value", "")
        family_name = name_data.get("family-name", {}).get("value", "")
        full_name = f"{given_names} {family_name}".strip()
        
        # Extract countries from addresses (nested in person)
        countries = set()
        addresses = person.get("addresses", {}).get("address", [])
        for addr in addresses:
            country = addr.get("country", {}).get("value")
            if country:
                countries.add(country)
        
        # Extract institutions and countries from employments/educations (root level)
        institutions = []
        
        # Check employments
        activities = data.get("activities-summary", {})
        employments = activities.get("employments", {}).get("affiliation-group", [])
        for emp_group in employments:
            summaries = emp_group.get("summaries", [])
            for summary in summaries:
                emp_summary = summary.get("employment-summary", {})
                org = emp_summary.get("organization", {})
                
                inst_name = org.get("name")
                inst_country = org.get("address", {}).get("country")
                
                if inst_name:
                    inst_data = {"name": inst_name}
                    if inst_country:
                        inst_data["country"] = inst_country
                        countries.add(inst_country)
                    institutions.append(inst_data)
        
        # Check education
        educations = activities.get("educations", {}).get("affiliation-group", [])
        for edu_group in educations:
            summaries = edu_group.get("summaries", [])
            for summary in summaries:
                edu_summary = summary.get("education-summary", {})
                org = edu_summary.get("organization", {})
                
                inst_name = org.get("name")
                inst_country = org.get("address", {}).get("country")
                
                if inst_name:
                    inst_data = {"name": inst_name}
                    if inst_country:
                        inst_data["country"] = inst_country
                        countries.add(inst_country)
                    institutions.append(inst_data)
        
        metadata = {
            "name": full_name,
            "given_name": given_names,
            "family_name": family_name,
            "countries": sorted(list(countries)),
            "institutions": institutions[:5],  # Limit to top 5
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        
        print(f"   ✅ ORCID metadata: {full_name} ({', '.join(countries) if countries else 'No country'})")
        return metadata
        
    except Exception as e:
        print(f"   ❌ Error fetching ORCID {orcid}: {str(e)}")
        return None


def extract_orcids_from_pdf_hyperlinks(pdf_bytes: bytes) -> List[str]:
    """
    Extract ORCIDs from PDF hyperlinks/annotations.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of ORCID identifiers found
    """
    orcids = set()
    orcid_pattern = re.compile(r'\b(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])\b', re.IGNORECASE)
    
    try:
        import io
        pdf = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        # Extract from annotations/hyperlinks
        for page in pdf.pages:
            if '/Annots' in page:
                try:
                    annotations = page['/Annots']
                    if annotations:
                        if hasattr(annotations, 'get_object'):
                            annotations = annotations.get_object()
                        
                        for annot in annotations:
                            try:
                                annot_obj = annot.get_object() if hasattr(annot, 'get_object') else annot
                                
                                if annot_obj and '/A' in annot_obj:
                                    action = annot_obj['/A']
                                    if hasattr(action, 'get_object'):
                                        action = action.get_object()
                                    
                                    if '/URI' in action:
                                        uri = str(action['/URI'])
                                        if 'orcid.org' in uri.lower():
                                            match = orcid_pattern.search(uri)
                                            if match:
                                                orcids.add(match.group(1))
                            except:
                                continue
                except:
                    continue
        
        return sorted(list(orcids))
        
    except Exception as e:
        print(f"   ⚠️  Error extracting ORCIDs from PDF: {e}")
        return []


def enrich_orcids_with_metadata(orcids: List[str]) -> Dict[str, Dict]:
    """
    Enrich a list of ORCIDs with metadata from ORCID API.
    
    Args:
        orcids: List of ORCID identifiers
        
    Returns:
        Dictionary mapping ORCID to metadata
    """
    metadata_map = {}
    
    print(f"\n🔍 Consultando API de ORCID para {len(orcids)} autores...")
    
    for idx, orcid in enumerate(orcids, 1):
        print(f"   [{idx}/{len(orcids)}] {orcid}")
        
        metadata = get_orcid_metadata(orcid)
        if metadata:
            metadata_map[orcid] = metadata
        else:
            # Store ORCID even if metadata fetch failed
            metadata_map[orcid] = {
                "name": None,
                "countries": [],
                "institutions": [],
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "fetch_error": True
            }
    
    print(f"   ✅ Metadata obtenida para {len([m for m in metadata_map.values() if not m.get('fetch_error')])} autores\n")
    
    return metadata_map
