#!/usr/bin/env python3
"""
Force re-enrichment by clearing cache for a specific DOI
"""
import requests
import os
from sqlalchemy import create_engine, text

# Database connection
os.environ.setdefault('DATABASE_URL', 'postgresql://cecan_user:cecan_password@localhost:5432/cecan_db')
engine = create_engine(os.environ['DATABASE_URL'])

BASE_URL = "http://localhost:8000"
GREEN = '\033[92m'
BLUE = '\033[94m'
RESET = '\033[0m'

def login():
    """Login and get token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@cecan.cl", "password": "admin123"}
    )
    return response.json()["access_token"] if response.status_code == 200 else None

def clear_cache_for_doi(doi):
    """Delete cached Scholar data for a specific DOI"""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM scholar_paper_data WHERE doi = :doi"),
            {"doi": doi}
        )
        conn.commit()
        print(f"{GREEN}✅ Deleted cache for DOI: {doi}{RESET}")
        return result.rowcount

def enrich_publication(token, pub_id):
    """Enrich a publication"""
    print(f"{BLUE}ℹ️  Enriching publication {pub_id}...{RESET}")
    
    response = requests.post(
        f"{BASE_URL}/api/publications/{pub_id}/enrich-scholar",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"{GREEN}✅ Status: {data.get('status')}{RESET}")
        return data
    else:
        print(f"❌ Error: {response.text}")
        return None

def get_scholar_data(token, pub_id):
    """Get Scholar data and show embedding dimensions"""
    response = requests.get(
        f"{BASE_URL}/api/publications/{pub_id}/scholar-data",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        embedding_dims = data.get('embedding_dimensions', 0)
        
        print("\n" + "="*70)
        print("📊 SCHOLAR DATA (AFTER RE-ENRICHMENT)")
        print("="*70)
        print(f"DOI: {data.get('doi')}")
        print(f"Title: {data.get('title')[:80]}...")
        print(f"Embedding Dimensions: {embedding_dims}")
        
        if embedding_dims > 0:
            print(f"{GREEN}🎉 SUCCESS! Embeddings with {embedding_dims} dimensions stored!{RESET}")
        else:
            print(f"⚠️  Still 0 dimensions - paper may not have embeddings in Scholar")
        
        print("="*70 + "\n")
        return data
    else:
        print(f"❌ Failed: {response.text}")
        return None

def main():
    print("\n" + "="*70)
    print("🔄 FORCE RE-ENRICHMENT (Clear Cache)")
    print("="*70 + "\n")
    
    # Publication to test (the one that was cached)
    pub_id = 277
    doi = "10.1177/17562848251325461"
    
    print(f"{BLUE}Target: Publication {pub_id} with DOI {doi}{RESET}\n")
    
    # 1. Clear cache
    deleted = clear_cache_for_doi(doi)
    if deleted == 0:
        print("⚠️  No cache found (already cleared or never enriched)\n")
    
    # 2. Login
    token = login()
    if not token:
        print("❌ Login failed")
        return
    
    print(f"{GREEN}✅ Login successful{RESET}\n")
    
    # 3. Force re-enrichment
    result = enrich_publication(token, pub_id)
    
    if not result:
        return
    
    # 4. Check embedding dimensions
    get_scholar_data(token, pub_id)
    
    print(f"{GREEN}✅ Test completed!{RESET}\n")

if __name__ == "__main__":
    main()
