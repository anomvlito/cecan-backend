
from database.session import get_db
from core.models import Publication
from sqlalchemy import text

db = next(get_db())

# Check total publications
total_pubs = db.query(Publication).count()
print(f"Total publications: {total_pubs}")

# Check status distribution
statuses = db.execute(text("SELECT enrichment_status, COUNT(*) FROM publications GROUP BY enrichment_status")).fetchall()
print("\nStatus distribution:")
for status, count in statuses:
    print(f"  {status}: {count}")

# Check actual embeddings in RAG service (simulated check since we can't easily introspect the in-memory RAG service from here without loading it fully, but let's check the publication model if it has any vector fields - the user mentioned 'embedding_vector')

# Wait, the previous analysis mentioned: "AttributeError: type object 'Publication' has no attribute 'embedding_vector'"
# So the embeddings are likely stored in the RAG service's chroma/faiss index or in a separate table, OR the model definition in the code I read doesn't return it.
# The code in research_map_service.py uses `self.rag_engine.pub_embeddings`. This suggests they are in-memory in the RAG engine? Or loaded from disk?

# Let's check if the RAG service can tell us anything.
try:
    from services.rag_service import get_semantic_engine
    rag_engine = get_semantic_engine()
    print(f"\nRAG Engine loaded.")
    print(f"RAG Engine pub_embeddings count: {len(rag_engine.pub_embeddings) if hasattr(rag_engine, 'pub_embeddings') else 'N/A'}")
    print(f"RAG Engine pub_chunks count: {len(rag_engine.pub_chunks) if hasattr(rag_engine, 'pub_chunks') else 'N/A'}")
except Exception as e:
    print(f"\nCould not load RAG engine details: {e}")
