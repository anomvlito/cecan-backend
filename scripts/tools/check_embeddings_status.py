#!/usr/bin/env python3
"""
Check how many papers have embeddings in the database
"""
import os
os.environ.setdefault('DATABASE_URL', 'postgresql://cecan_user:cecan_password@localhost:5432/cecan_db')

from sqlalchemy import create_engine, text
from core.models import ScholarPaperData

engine = create_engine(os.environ['DATABASE_URL'])

print("\n" + "="*70)
print("📊 SCHOLAR EMBEDDINGS DATABASE STATUS")
print("="*70 + "\n")

with engine.connect() as conn:
    # Total papers with Scholar data
    total = conn.execute(
        text("SELECT COUNT(*) FROM scholar_paper_data")
    ).scalar()
    
    print(f"Total papers in scholar_paper_data: {total}")
    
    # Papers with embeddings (non-null and non-empty)
    with_embeddings = conn.execute(
        text("""
            SELECT COUNT(*) 
            FROM scholar_paper_data 
            WHERE embedding_vector IS NOT NULL 
            AND json_array_length(embedding_vector) > 0
        """)
    ).scalar()
    
    print(f"Papers WITH embeddings: {with_embeddings}")
    
    # Papers without embeddings
    without = total - with_embeddings
    print(f"Papers WITHOUT embeddings: {without}")
    
    # Check embedding dimensions distribution
    dims_result = conn.execute(
        text("""
            SELECT json_array_length(embedding_vector) as dims, COUNT(*) as count
            FROM scholar_paper_data 
            WHERE embedding_vector IS NOT NULL
            GROUP BY dims
            ORDER BY dims
        """)
    ).fetchall()
    
    if dims_result:
        print("\n📐 Embedding dimensions breakdown:")
        for row in dims_result:
            print(f"  - {row[0]} dimensions: {row[1]} papers")
    
    # Enrichment status breakdown
    status_result = conn.execute(
        text("""
            SELECT enrichment_status, COUNT(*) 
            FROM scholar_paper_data 
            GROUP BY enrichment_status
        """)
    ).fetchall()
    
    print("\n📊 Enrichment status:")
    for row in status_result:
        print(f"  - {row[0]}: {row[1]} papers")
    
    print("\n" + "="*70)
    print("🎯 RECOMMENDATION:")
    print("="*70 + "\n")
    
    if with_embeddings >= 50:
        print("✅ GREAT! You have enough papers for a meaningful 3D visualization")
        print(f"   {with_embeddings} papers → K-means clustering will be significant")
        print("   → Proceed with full implementation (2D/3D adaptive)")
    elif with_embeddings >= 30:
        print("⚠️  MARGINAL. Consider these options:")
        print(f"   - {with_embeddings} papers → Start with 2D visualization")
        print("   - Enrich more papers first, then upgrade to 3D")
        print("   - Create demo with current data for stakeholder feedback")
    elif with_embeddings >= 10:
        print("⚠️  TOO FEW for production visualization")
        print(f"   - {with_embeddings} papers → Clustering won't be meaningful")
        print("   - RECOMMENDATION: Enrich at least 30 papers first")
        print("   - Or: Create synthetic demo to validate UX approach")
    else:
        print("❌ NOT ENOUGH DATA")
        print(f"   - Only {with_embeddings} papers with embeddings")
        print("   - Focus on batch enrichment first")
        print(f"   - Target: Enrich at least {max(30 - with_embeddings, 0)} more papers")
    
    print("\n💡 Next steps:")
    if with_embeddings < 30:
        print("   1. Run batch enrichment on existing publications with DOIs")
        print(f"   2. Target: Get to at least 30 papers with embeddings")
        print("   3. Then revisit Research Constellation Map implementation")
        print("\n   Quick batch enrich command:")
        print("   → Use /api/publications/batch-enrich-scholar endpoint")
    else:
        print("   1. ✅ You're ready! Start with ResearchMapSnapshot model")
        print("   2. Create UMAP + K-means backend endpoint")
        print("   3. Build Plotly frontend (2D/3D adaptive)")
    
    print()

print(f"\n📈 Total publications in main table (for reference):")
with engine.connect() as conn:
    pub_total = conn.execute(text("SELECT COUNT(*) FROM publications")).scalar()
    pub_with_doi = conn.execute(
        text("SELECT COUNT(*) FROM publications WHERE canonical_doi IS NOT NULL")
    ).scalar()
    
    print(f"   - Total publications: {pub_total}")
    print(f"   - Publications with DOI: {pub_with_doi}")
    print(f"   - Enrichable papers: {pub_with_doi - with_embeddings}")
    
print("\n" + "="*70 + "\n")
