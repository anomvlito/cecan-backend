#!/usr/bin/env python3
"""
Test Scholar Enrichment - Smart Version
Finds a publication with DOI and enriches it
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def login():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": "admin@cecan.cl", "password": "admin123"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print_success(f"Login successful!")
        return token
    else:
        print_error(f"Login failed: {response.text}")
        return None

def get_publications(token):
    """Get all publications"""
    print_info("Fetching publications...")
    
    response = requests.get(
        f"{BASE_URL}/api/publications",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        pubs = response.json()
        print_success(f"Found {len(pubs)} publications")
        return pubs
    else:
        print_error(f"Failed to get publications: {response.text}")
        return []

def find_publication_with_doi(pubs):
    """Find first publication with a DOI"""
    for pub in pubs:
        if pub.get('canonical_doi'):
            return pub
    return None

def enrich_publication(token, pub_id):
    """Enrich a publication with Scholar data"""
    print_info(f"Enriching publication {pub_id}...")
    
    response = requests.post(
        f"{BASE_URL}/api/publications/{pub_id}/enrich-scholar",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        status = data.get('status')
        
        if status == 'enriched':
            print_success("✨ Successfully enriched with Scholar data!")
        elif status == 'cached':
            print_success("📦 Using cached Scholar data")
        elif status == 'not_found':
            print_error("Paper not found in Semantic Scholar")
        elif status == 'no_doi':
            print_error("Publication has no DOI")
        else:
            print_error(f"Status: {status}")
        
        return data
    else:
        print_error(f"API Error: {response.text}")
        return None

def get_scholar_data(token, pub_id):
    """Get cached Scholar data"""
    response = requests.get(
        f"{BASE_URL}/api/publications/{pub_id}/scholar-data",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n" + "="*70)
        print("📊 SCHOLAR DATA")
        print("="*70)
        print(f"DOI: {data.get('doi')}")
        print(f"Semantic Scholar ID: {data.get('semantic_scholar_id')}")
        print(f"Title: {data.get('title')}")
        print(f"Year: {data.get('year')}")
        print(f"Status: {data.get('status')}")
        print(f"Authors: {len(data.get('authors', []))} authors")
        print(f"Embedding Dimensions: {data.get('embedding_dimensions')}")
        print(f"Citation Count: {data.get('citation_count')}")
        
        tldr = data.get('tldr')
        if tldr:
            print(f"\n📝 TLDR: {tldr[:200]}{'...' if len(tldr) > 200 else ''}")
        
        intent = data.get('intent_breakdown')
        if intent:
            print(f"\n📚 Citation Intents:")
            for intent_type, count in intent.items():
                print(f"  - {intent_type}: {count}")
        
        graph = data.get('reference_graph')
        if graph and graph.get('nodes'):
            print(f"\n🕸️  Reference Graph: {len(graph['nodes'])} nodes, {len(graph['links'])} links")
        
        print("="*70 + "\n")
        
        return data
    else:
        print_error(f"Failed: {response.text}")
        return None

def main():
    print("\n" + "="*70)
    print("🔬 SCHOLAR ENRICHMENT - SMART TESTER")
    print("="*70 + "\n")
    
    # 1. Login
    token = login()
    if not token:
        return
    
    # 2. Get publications
    pubs = get_publications(token)
    if not pubs:
        print_error("No publications found in database")
        return
    
    # 3. Find one with DOI
    pub_with_doi = find_publication_with_doi(pubs)
    
    if not pub_with_doi:
        print_error("No publications with DOI found!")
        print_info("Please upload a PDF with DOI or add one manually")
        return
    
    pub_id = pub_with_doi['id']
    doi = pub_with_doi['canonical_doi']
    title = pub_with_doi['title']
    
    print(f"\n{BLUE}📄 Selected Publication:{RESET}")
    print(f"  ID: {pub_id}")
    print(f"  DOI: {doi}")
    print(f"  Title: {title[:80]}...")
    print()
    
    # 4. Enrich
    result = enrich_publication(token, pub_id)
    
    if not result:
        return
    
    print()
    
    # 5. Show data
    if result.get('status') in ['enriched', 'cached']:
        get_scholar_data(token, pub_id)
    
    print_success("Test completed!\n")

if __name__ == "__main__":
    main()
