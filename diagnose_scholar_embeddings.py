#!/usr/bin/env python3
"""
Diagnose Scholar API response - Check what fields are actually returned
"""
import asyncio
import os
from modules.scholar.client import SemanticScholarClient

async def diagnose_api_response(doi):
    """Check what Scholar API actually returns"""
    
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    client = SemanticScholarClient(api_key=api_key)
    
    print(f"🔍 Fetching data for DOI: {doi}\n")
    print("="*70)
    
    # Fetch paper intelligence
    result = await client.get_paper_intelligence(doi)
    
    # Check key fields
    print(f"Paper ID: {result.get('paperId')}")
    print(f"Title: {result.get('title')[:80]}...")
    print(f"Year: {result.get('year')}")
    print()
    
    # Check embedding
    print("🧬 EMBEDDING CHECK:")
    raw_embedding = result.get('embedding_sample', [])
    print(f"  Raw embedding_sample field: {raw_embedding}")
    print(f"  Type: {type(raw_embedding)}")
    print(f"  Length: {len(raw_embedding) if isinstance(raw_embedding, list) else 0}")
    print()
    
    # Check if there's a full embedding anywhere
    print("🔎 Searching for full embedding in response...")
    
    # Print all keys in response
    print(f"\n📋 All keys in response: {list(result.keys())}")
    
    # Check TLDR
    tldr = result.get('tldr')
    print(f"\n📝 TLDR: {tldr[:100] if tldr else 'None'}...")
    
    # Check citations
    citations = result.get('smart_citations', [])
    print(f"\n📚 Smart citations: {len(citations)}")
    
    # Intent breakdown
    intent = result.get('intent_breakdown', {})
    print(f"\n🎯 Intent breakdown: {intent}")
    
    print("\n" + "="*70)
    print("\n💡 DIAGNOSIS:")
    
    if not raw_embedding or len(raw_embedding) == 0:
        print("❌ No embeddings returned by Semantic Scholar API")
        print("\nPossible reasons:")
        print("  1. Paper is too new (2025) - embeddings not generated yet")
        print("  2. This paper doesn't have embeddings in Scholar's database")
        print("  3. Embeddings require special API access or different endpoint")
        print("\nℹ️  This is NORMAL - not all papers have embeddings.")
    else:
        print(f"✅ Embeddings found! ({len(raw_embedding)} dimensions)")

async def main():
    # Test with the publication that was enriched
    doi = "10.1177/17562848251325461"
    
    await diagnose_api_response(doi)
    
    print("\n" + "="*70)
    print("💡 TIP: Try with an older, well-cited paper:")
    print("   Example: 10.1038/nature12373 (famous CRISPR paper)")
    
    # Test with a famous paper
    print("\n\nTesting with famous paper...")
    print("="*70)
    await diagnose_api_response("10.1038/nature12373")

if __name__ == "__main__":
    asyncio.run(main())
