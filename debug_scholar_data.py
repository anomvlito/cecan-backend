
from database.session import get_db
from core.models import Publication, ScholarPaperData
from sqlalchemy import text
import sys

db = next(get_db())

print("🔍 Checking ScholarPaperData...")

# Check total scholar data
scholar_count = db.query(ScholarPaperData).count()
print(f"Total ScholarPaperData entries: {scholar_count}")

# Check entries with embeddings
embedding_count = db.query(ScholarPaperData).filter(ScholarPaperData.embedding_vector.isnot(None)).count()
print(f"Entries with embeddings: {embedding_count}")

# Check linked entries
linked_count = db.query(ScholarPaperData).filter(
    ScholarPaperData.embedding_vector.isnot(None),
    ScholarPaperData.publication_id.isnot(None)
).count()
print(f"Entries with embeddings AND linked to publication: {linked_count}")

if linked_count < 10:
    print("❌ Not enough data for map generation (< 10)")
    # Print some DOIs to debug
    print("\nSample DOIs in Scholar Table:")
    for row in db.query(ScholarPaperData).limit(5):
        print(f"  - DOI: {row.doi}, Embed: {bool(row.embedding_vector)}, PubID: {row.publication_id}")
else:
    print(f"✅ Ready for map generation! ({linked_count} valid entries)")

print("\nChecking Publication status...")
pub_status = db.query(Publication.enrichment_status, backend_func=text("count(*)")).group_by(Publication.enrichment_status).all()
# Note: group_by query syntax might need adjustment, simpler:
results = db.execute(text("SELECT enrichment_status, COUNT(*) FROM publications GROUP BY enrichment_status")).fetchall()
for row in results:
    print(f"  {row[0]}: {row[1]}")
