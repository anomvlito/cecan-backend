#!/usr/bin/env python3
"""
Diagnostic: Show why names aren't matching between OpenAlex and DB
"""
import sys
import json
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from core.models import AcademicMember, ResearcherDetails

def normalize(text):
    if not text: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                 if unicodedata.category(c) != 'Mn').lower().strip()

def smart_match(name1, name2):
    n1 = normalize(name1)
    n2 = normalize(name2)
    
    if n1 == n2: return 1.0
    
    parts1 = n1.split()
    parts2 = n2.split()
    
    if len(parts1) < 2 or len(parts2) < 2:
        return SequenceMatcher(None, n1, n2).ratio()
    
    surnames1 = parts1[1:]
    surnames2 = parts2[1:]
    common_surname = set(surnames1) & set(surnames2)
    
    if parts1[0] == parts2[0] and common_surname:
        return 0.95
        
    if (parts1[0][0] == parts2[0][0]) and common_surname:
         return 0.85
         
    if n1 in n2 or n2 in n1:
        return 0.90
        
    return SequenceMatcher(None, n1, n2).ratio()

def diagnose_matching():
    db = SessionLocal()
    
    try:
        # Load enriched JSON
        json_path = Path("data/enriched_orcids.json")
        if not json_path.exists():
            print("❌ enriched_orcids.json not found")
            return
            
        with open(json_path, 'r', encoding='utf-8') as f:
            enriched_data = json.load(f)
        
        # Get active researchers without ORCID
        researchers_without_orcid = db.query(AcademicMember).outerjoin(ResearcherDetails).filter(
            AcademicMember.member_type == 'researcher',
            AcademicMember.is_active == True,
            (ResearcherDetails.orcid.is_(None)) | (ResearcherDetails.orcid == '')
        ).all()
        
        print("=" * 80)
        print(f"🔍 Matching Diagnostic for {len(researchers_without_orcid)} researchers without ORCID")
        print("=" * 80)
        
        # Take first 10 for debugging
        for db_researcher in researchers_without_orcid[:10]:
            print(f"\n📌 DB: {db_researcher.full_name} (ID: {db_researcher.id})")
            
            best_match = None
            best_score = 0
            best_orcid_name = None
            
            for item in enriched_data:
                if item.get("status") != "success":
                    continue
                    
                orcid_name = item.get("display_name", "")
                if not orcid_name:
                    continue
                
                score = smart_match(db_researcher.full_name, orcid_name)
                
                if score > best_score:
                    best_score = score
                    best_match = item
                    best_orcid_name = orcid_name
            
            if best_match:
                print(f"   Best match: {best_orcid_name}")
                print(f"   Score: {best_score:.2f}")
                print(f"   ORCID: {best_match.get('orcid')}")
                if best_score > 0.70:
                    print(f"   ✅ WOULD MATCH (threshold 0.70)")
                else:
                    print(f"   ❌ Below threshold")
            else:
                print(f"   ❌ No match found")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_matching()
