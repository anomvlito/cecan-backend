"""
Test compliance report endpoint
"""
import sqlite3
import os
import sys

# Add project root to path to find backend module if needed
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get compliance stats
cursor.execute("SELECT COUNT(*) as total FROM Publicaciones WHERE contenido_texto IS NOT NULL")
total_with_text = cursor.fetchone()['total']

cursor.execute("SELECT COUNT(*) as count FROM Publicaciones WHERE anid_report_status = 'Ok'")
ok_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM Publicaciones WHERE anid_report_status = 'Warning'")
warning_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM Publicaciones WHERE anid_report_status = 'Error'")
error_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM Publicaciones WHERE has_valid_affiliation = 1")
aff_count = cursor.fetchone()['count']

cursor.execute("SELECT COUNT(*) as count FROM Publicaciones WHERE has_funding_ack = 1")
fund_count = cursor.fetchone()['count']

# Get non-compliant publications (WARNING or ERROR)
cursor.execute("""
    SELECT id, titulo, anid_report_status, audit_notes, has_valid_affiliation, has_funding_ack
    FROM Publicaciones 
    WHERE anid_report_status IN ('Warning', 'Error')
    ORDER BY anid_report_status DESC, id
""")

non_compliant = cursor.fetchall()

print("COMPLIANCE REPORT DATA:")
print("=" * 70)
print(f"\nTotal with text: {total_with_text}")
print(f"Status breakdown:")
print(f"  OK:      {ok_count}")
print(f"  WARNING: {warning_count}")
print(f"  ERROR:   {error_count}")
print(f"\nHas affiliation: {aff_count}")
print(f"Has funding:     {fund_count}")

if total_with_text > 0:
    compliance_rate = (ok_count / total_with_text) * 100
    print(f"\nCompliance Rate: {compliance_rate:.1f}%")

print(f"\n\nNON-COMPLIANT PUBLICATIONS ({len(non_compliant)}):")
print("=" * 70)

for pub in non_compliant:
    print(f"\n[{pub['anid_report_status']}] ID: {pub['id']}")
    print(f"  Title: {pub['titulo'][:80]}...")
    print(f"  Has Affiliation: {pub['has_valid_affiliation']}")
    print(f"  Has Funding: {pub['has_funding_ack']}")
    print(f"  Notes: {pub['audit_notes']}")

conn.close()
