#!/usr/bin/env python3
"""
Final diagnostic: Which of the 60 missing are in the JSON vs not
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

def final_diagnostic():
    db = SessionLocal()
    
    try:
        # Load enriched JSON
        json_path = Path("data/enriched_orcids.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            enriched_data = json.load(f)
        
        successful_orcids = [item for item in enriched_data if item.get("status") == "success"]
        
        # Get active researchers without ORCID
        researchers_without_orcid = db.query(AcademicMember).join(ResearcherDetails).filter(
            AcademicMember.member_type == 'researcher',
            AcademicMember.is_active == True,
            ResearcherDetails.category.in_(['Principal', 'Asociado', 'Adjunto']),
            (ResearcherDetails.orcid.is_(None)) | (ResearcherDetails.orcid == '')
        ).all()
        
        print("=" * 80)
        print(f"🔍 Final Diagnostic: {len(researchers_without_orcid)} missing ORCIDs")
        print("=" * 80)
        
        could_match = []
        no_match_found = []
        
        for db_researcher in researchers_without_orcid:
            best_match = None
            best_score = 0
            best_orcid_name = None
            
            for item in successful_orcids:
                orcid_name = item.get("display_name", "")
                if not orcid_name:
                    continue
                
                score = smart_match(db_researcher.full_name, orcid_name)
                
                if score > best_score:
                    best_score = score
                    best_match = item
                    best_orcid_name = orcid_name
            
            if best_match and best_score > 0.50:  # Threshold for "could be"
                could_match.append({
                    "db_name": db_researcher.full_name,
                    "orcid_name": best_orcid_name,
                    "score": best_score,
                    "orcid": best_match.get("orcid"),
                    "would_match": best_score > 0.70
                })
            else:
                no_match_found.append(db_researcher.full_name)
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Could potentially match (score > 0.50): {len(could_match)}")
        print(f"   ❌ No match found in ORCID data: {len(no_match_found)}")
        
        if could_match:
            print(f"\n💡 Potential matches (may need manual review):")
            for item in could_match[:15]:  # Show first 15
                status = "✅ WOULD" if item["would_match"] else "⚠️  MAYBE"
                print(f"   {status} {item['db_name']} ≈ {item['orcid_name']} ({item['score']:.2f})")
        
        if no_match_found:
            print(f"\n❌ No ORCID found (not in CSV or name too different):")
            for name in no_match_found[:20]:  # Show first 20
                print(f"   - {name}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    final_diagnostic()
