"""
Test compliance audit without SQLAlchemy enums
"""
import sqlite3
import re
import os
import sys
from datetime import datetime

# Add project root to path to find backend module if needed
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

# Affiliation patterns
AFFILIATION_PATTERNS = [
    r"Center for Cancer Prevention",
    r"Centro de Prevención del Cáncer",
    r"CECAN",
    r"Pontificia Universidad Católica de Chile",
    r"UC Chile",
    r"Facultad de Medicina UC"
]

# Funding patterns
FUNDING_PATTERNS = [
    r"FONDAP\s*1?52220002",
    r"FONDAP\s*15220002",
    r"ANID",
    r"Agencia Nacional de Investigación y Desarrollo"
]

def validate_affiliation(text):
    if not text:
        return False, []
    
    found = []
    for pattern in AFFILIATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(pattern)
    
    return len(found) > 0, found

def validate_funding(text):
    if not text:
        return False, []
    
    found = []
    for pattern in FUNDING_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(pattern)
    
    return len(found) > 0, found

def determine_status(has_aff, has_fund):
    if has_aff and has_fund:
        return "Ok"
    elif has_aff or has_fund:
        return "Warning"
    else:
        return "Error"

print("CECAN Compliance Robot - Test Audit")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get publications with content
cursor.execute("SELECT id, titulo, contenido_texto FROM Publicaciones WHERE contenido_texto IS NOT NULL AND contenido_texto != ''")
publications = cursor.fetchall()

print(f"\nFound {len(publications)} publications to audit\n")

stats = {
    "total": len(publications),
    "ok": 0,
    "warning": 0,
    "error": 0,
    "has_aff": 0,
    "has_fund": 0
}

for i, (pub_id, titulo, texto) in enumerate(publications, 1):  # ALL publications
    has_aff, aff_matches = validate_affiliation(texto)
    has_fund, fund_matches = validate_funding(texto)
    status = determine_status(has_aff, has_fund)
    
    if status == "Ok":
        stats["ok"] += 1
    elif status == "Warning":
        stats["warning"] += 1
    else:
        stats["error"] += 1
    
    if has_aff:
        stats["has_aff"] += 1
    if has_fund:
        stats["has_fund"] += 1
    
    # Generate notes
    notes = []
    if has_aff:
        notes.append(f"[OK] Affiliation: {', '.join(aff_matches[:2])}")
    else:
        notes.append("[ERROR] No affiliation found")
    
    if has_fund:
        notes.append(f"[OK] Funding: {', '.join(fund_matches[:2])}")
    else:
        notes.append("[ERROR] No funding found")
    
    audit_notes = " | ".join(notes)
    
    # Update database
    cursor.execute("""
        UPDATE Publicaciones
        SET has_valid_affiliation = ?,
            has_funding_ack = ?,
            anid_report_status = ?,
            last_audit_date = ?,
            audit_notes = ?
        WHERE id = ?
    """, (has_aff, has_fund, status, datetime.utcnow().isoformat(), audit_notes, pub_id))
    
    # Only print details for first 10
    if i <= 10:
        print(f"\n[{status}] {titulo[:60]}...")
        print(f"  {audit_notes}")
    elif i % 20 == 0:
        print(f"  ... processed {i} publications ...")

conn.commit()
conn.close()

print("\n" + "=" * 70)
print("\nFULL AUDIT SUMMARY:")
print(f"  Total audited:   {stats['total']}")
print(f"  [OK]:            {stats['ok']}")
print(f"  [WARNING]:       {stats['warning']}")
print(f"  [ERROR]:         {stats['error']}")
print(f"\n  Has affiliation: {stats['has_aff']}")
print(f"  Has funding:     {stats['has_fund']}")

if stats['total'] > 0:
    compliance_rate = (stats['ok'] / stats['total']) * 100
    print(f"\n  Compliance Rate: {compliance_rate:.1f}%")

print("\n[SUCCESS] Full audit completed!")
