#!/usr/bin/env python3
"""
ORCID Batch Enrichment Script
Reads ORCIDs from CSV, enriches with OpenAlex, creates AcademicMember records
"""
import csv
import json
import time
import re
import sys
from pathlib import Path
from typing import List, Dict, Set
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, ResearcherDetails

# OpenAlex Configuration
OPENALEX_API_BASE = "https://api.openalex.org"
OPENALEX_EMAIL = "your-email@example.com"  # Polite pool
POLITENESS_DELAY = 0.1  # 100ms between requests

def extract_unique_orcids(csv_path: str) -> Set[str]:
    """Extract all unique ORCIDs from the CSV file"""
    unique_orcids = set()
    orcid_pattern = re.compile(r'\d{4}-\d{4}-\d{4}-\d{3}[0-9X]')
    
    print(f"📄 Reading CSV: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Column name: "Todos los ORCIDs"
            orcids_str = row.get("Todos los ORCIDs", "")
            if orcids_str:
                # Split by comma and clean
                found_orcids = orcid_pattern.findall(orcids_str)
                unique_orcids.update(found_orcids)
    
    print(f"✅ Found {len(unique_orcids)} unique ORCIDs")
    return unique_orcids


def enrich_orcid_with_openalex(orcid: str) -> Dict:
    """Fetch author metadata from OpenAlex by ORCID"""
    url = f"{OPENALEX_API_BASE}/authors/orcid:{orcid}"
    headers = {"User-Agent": f"CECAN-Research-Platform (mailto:{OPENALEX_EMAIL})"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return {"status": "not_found", "orcid": orcid}
        
        if response.status_code != 200:
            return {"status": "error", "orcid": orcid, "error": f"HTTP {response.status_code}"}
        
        data = response.json()
        
        # Extract key fields
        enriched = {
            "status": "success",
            "orcid": orcid,
            "display_name": data.get("display_name", ""),
            "works_count": data.get("works_count", 0),
            "cited_by_count": data.get("cited_by_count", 0),
            "h_index": data.get("summary_stats", {}).get("h_index", 0),
            "i10_index": data.get("summary_stats", {}).get("i10_index", 0),
            "last_known_institution": None,
            "openalex_id": data.get("id", ""),
        }
        
        # Extract affiliation (last known institution)
        affiliations = data.get("affiliations", [])
        if affiliations and len(affiliations) > 0:
            enriched["last_known_institution"] = affiliations[0].get("institution", {}).get("display_name")
        
        return enriched
    
    except Exception as e:
        return {"status": "error", "orcid": orcid, "error": str(e)}


def enrich_all_orcids(orcids: Set[str]) -> List[Dict]:
    """Enrich all ORCIDs with OpenAlex data"""
    enriched_list = []
    total = len(orcids)
    
    print(f"\n🔍 Enriching {total} ORCIDs with OpenAlex...")
    
    for idx, orcid in enumerate(sorted(orcids), 1):
        print(f"  [{idx}/{total}] {orcid}...", end=" ")
        
        result = enrich_orcid_with_openalex(orcid)
        enriched_list.append(result)
        
        if result["status"] == "success":
            print(f"✅ {result['display_name']} (h={result['h_index']})")
        elif result["status"] == "not_found":
            print("⚠️  Not found in OpenAlex")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown')}")
        
        # Politeness delay
        time.sleep(POLITENESS_DELAY)
    
    return enriched_list


def create_researchers_from_enriched(enriched_data: List[Dict], db, auto_create: bool = True):
    """Create AcademicMember records from enriched ORCID data"""
    from difflib import SequenceMatcher
    
    created = 0
    updated = 0
    skipped = 0
    errors = 0
    
    print(f"\n👥 Creating/Updating Researchers (auto_create={auto_create})...")
    
    for data in enriched_data:
        if data["status"] != "success":
            skipped += 1
            continue
        
        orcid = data["orcid"]
        display_name = data["display_name"]
        
        if not display_name:
            print(f"  ⚠️  Skipping {orcid}: No display name")
            skipped += 1
            continue
        
        try:
            # Check if researcher already exists BY ORCID (only active ones!)
            existing_member = db.query(AcademicMember).join(ResearcherDetails).filter(
                ResearcherDetails.orcid == orcid,
                AcademicMember.is_active == True  # CRITICAL: Only update active researchers
            ).first()
            
            if existing_member:
                # Update metrics
                details = existing_member.researcher_details
                details.indice_h = data["h_index"]
                details.citaciones_totales = data["cited_by_count"]
                details.works_count = data["works_count"]
                details.i10_index = data["i10_index"]
                details.last_openalex_sync = datetime.utcnow()
                
                db.commit()
                print(f"  🔄 Updated: {display_name} (ORCID: {orcid})")
                updated += 1
            else:
                # ORCID not found, check for SIMILAR NAMES (fuzzy matching)
                # Filter for ACTIVE researchers with CATEGORY (Principal/Asociado/Adjunto)
                researchers_without_orcid = db.query(AcademicMember).join(ResearcherDetails).filter(
                    AcademicMember.member_type == 'researcher',
                    AcademicMember.is_active == True,
                    ResearcherDetails.category.in_(['Principal', 'Asociado', 'Adjunto']),
                    (ResearcherDetails.orcid.is_(None)) | (ResearcherDetails.orcid == '')
                ).all()
                
                best_match = None
                best_similarity = 0
                
                # Helper to normalize names (remove accents, lowercase)
                import unicodedata
                def normalize(text):
                    if not text: return ""
                    return ''.join(c for c in unicodedata.normalize('NFD', text)
                                 if unicodedata.category(c) != 'Mn').lower().strip()

                def smart_match(name1, name2):
                    n1 = normalize(name1)
                    n2 = normalize(name2)
                    
                    # 1. Exact match normalized
                    if n1 == n2: return 1.0
                    
                    # Tokenize
                    parts1 = n1.split()
                    parts2 = n2.split()
                    
                    if len(parts1) < 2 or len(parts2) < 2:
                        return SequenceMatcher(None, n1, n2).ratio()
                        
                    # 2. Match First Name + First Surname (ignoring middle name/second surname)
                    # Assumes format: [First] [Middle?] [Last1] [Last2?]
                    # We check if Name1+Last1 matches Name2+Last2
                    
                    first1, last1 = parts1[0], parts1[-1]  # Or parts1[1] if we want stricter
                    first2, last2 = parts2[0], parts2[-1]
                    
                    # Find surname intersection
                    # Check if ANY surname from name1 exists in name2
                    surnames1 = parts1[1:]
                    surnames2 = parts2[1:]
                    
                    common_surname = set(surnames1) & set(surnames2)
                    
                    if parts1[0] == parts2[0] and common_surname:
                        return 0.95 # High confidence: Same first name + at least one common surname
                        
                    # 3. Initials match (e.g. "j. perez" vs "juan perez")
                    if (parts1[0][0] == parts2[0][0]) and common_surname:
                         return 0.85 # Medium confidence: Same initial + common surname
                         
                    # 4. Contains logic (string subset)
                    if n1 in n2 or n2 in n1:
                        return 0.90
                        
                    return SequenceMatcher(None, n1, n2).ratio()

                norm_display_name = normalize(display_name)
                
                for candidate in researchers_without_orcid:
                    similarity = smart_match(candidate.full_name, display_name)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = candidate
                
                # Lower threshold to 0.70 for smart matching
                if best_match and best_similarity > 0.70:
                    print(f"  🔗 MATCH FOUND: '{display_name}' ≈ '{best_match.full_name}' ({best_similarity*100:.1f}%)")
                    
                    # Add ORCID to existing researcher
                    if not best_match.researcher_details:
                        details = ResearcherDetails(
                            member_id=best_match.id,
                            orcid=orcid,
                            indice_h=data["h_index"],
                            citaciones_totales=data["cited_by_count"],
                            works_count=data["works_count"],
                            i10_index=data["i10_index"],
                            last_openalex_sync=datetime.utcnow()
                        )
                        db.add(details)
                    else:
                        best_match.researcher_details.orcid = orcid
                        best_match.researcher_details.indice_h = data["h_index"]
                        best_match.researcher_details.citaciones_totales = data["cited_by_count"]
                        best_match.researcher_details.works_count = data["works_count"]
                        best_match.researcher_details.i10_index = data["i10_index"]
                        best_match.researcher_details.last_openalex_sync = datetime.utcnow()
                    
                    db.commit()
                    print(f"  ✅ Linked ORCID to existing researcher: {best_match.full_name}")
                    updated += 1
                    continue
                
                # No match found, create NEW researcher
                if not auto_create:
                    print(f"  🔍 Preview: Would create {display_name} (ORCID: {orcid})")
                    continue
                
                new_member = AcademicMember(
                    full_name=display_name,
                    member_type="researcher",
                    institution=data.get("last_known_institution") or "Unknown",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_member)
                db.flush()  # Get ID
                
                # Create ResearcherDetails
                details = ResearcherDetails(
                    member_id=new_member.id,
                    orcid=orcid,
                    indice_h=data["h_index"],
                    citaciones_totales=data["cited_by_count"],
                    works_count=data["works_count"],
                    i10_index=data["i10_index"],
                    last_openalex_sync=datetime.utcnow()
                )
                db.add(details)
                db.commit()
                
                print(f"  ✅ Created: {display_name} (ORCID: {orcid})")
                created += 1
        
        except Exception as e:
            db.rollback()
            print(f"  ❌ Error with {orcid}: {e}")
            errors += 1
    
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrich ORCIDs and create researchers")
    parser.add_argument("--csv", default="data/orcid_extraction_report_20260105_012133.csv", help="CSV file path")
    parser.add_argument("--auto-create", action="store_true", help="Automatically create researchers (no preview)")
    parser.add_argument("--output", default="data/enriched_orcids.json", help="JSON output path")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔬 ORCID Batch Enrichment Script")
    print("=" * 60)
    
    # Step 1: Extract ORCIDs
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return
    
    unique_orcids = extract_unique_orcids(str(csv_path))
    
    # Step 2: Enrich with OpenAlex
    enriched_data = enrich_all_orcids(unique_orcids)
    
    # Save to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved enriched data to: {output_path}")
    
    # Summary
    success_count = sum(1 for d in enriched_data if d["status"] == "success")
    not_found_count = sum(1 for d in enriched_data if d["status"] == "not_found")
    error_count = sum(1 for d in enriched_data if d["status"] == "error")
    
    print(f"\n📊 Enrichment Summary:")
    print(f"   ✅ Success: {success_count}")
    print(f"   ⚠️  Not Found: {not_found_count}")
    print(f"   ❌ Errors: {error_count}")
    
    # Step 3: Create researchers
    if success_count > 0:
        db = SessionLocal()
        try:
            result = create_researchers_from_enriched(enriched_data, db, args.auto_create)
            
            print(f"\n📊 Researcher Import Summary:")
            print(f"   ✅ Created: {result['created']}")
            print(f"   🔄 Updated: {result['updated']}")
            print(f"   ⏭️  Skipped: {result['skipped']}")
            print(f"   ❌ Errors: {result['errors']}")
        finally:
            db.close()
    
    print("\n✅ Script completed!")


if __name__ == "__main__":
    main()
