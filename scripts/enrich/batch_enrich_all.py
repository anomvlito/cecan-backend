#!/usr/bin/env python3
"""
Batch Enrich All Publications with Scholar Data
"""
import asyncio
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from core.models import Publication, ScholarPaperData
from services.scholar_enrichment import ScholarEnrichmentService

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://cecan_user:cecan_password@localhost:5432/cecan_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

async def process_publications():
    db = SessionLocal()
    try:
        print(f"\n{BOLD}🔬 SCHOLAR BATCH ENRICHMENT{RESET}")
        print("=" * 60)
        
        # 1. Get all publications with DOIs
        print(f"{BLUE}ℹ️  Fetching publications with DOIs...{RESET}")
        pubs = db.query(Publication).filter(Publication.canonical_doi.isnot(None)).all()
        total_pubs = len(pubs)
        
        if total_pubs == 0:
            print(f"{YELLOW}⚠️  No publications with DOIs found.{RESET}")
            return

        print(f"{GREEN}✅ Found {total_pubs} publications with DOIs.{RESET}")
        print("=" * 60)
        
        # 2. Initialize Service
        service = ScholarEnrichmentService(db)
        
        # 3. Process Loop
        success_count = 0
        cached_count = 0
        failed_count = 0
        
        start_time = time.time()
        
        print_progress_bar(0, total_pubs, prefix='Progress:', suffix='Complete', length=40)
        
        for i, pub in enumerate(pubs):
            try:
                # Force 1.1s delay to respect rate limit (1 req/sec)
                await asyncio.sleep(1.1)
                
                result = await service.enrich_publication(pub.id)
                status = result.get('status')
                
                if status == 'enriched':
                    success_count += 1
                elif status == 'cached':
                    cached_count += 1
                else:
                    failed_count += 1
                    # Optional: Print error details if needed, but keeping it clean for progress bar
                    # print(f"Failed: {result.get('error')}")
                
            except Exception as e:
                failed_count += 1
                # print(f"Error processing {pub.id}: {e}")
            
            # Update progress bar
            print_progress_bar(i + 1, total_pubs, prefix='Progress:', suffix=f'({i+1}/{total_pubs})', length=40)
            
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print(f"{BOLD}🎉 BATCH ENRICHMENT COMPLETED{RESET}")
        print(f"⏱️  Time elapsed: {elapsed_time:.2f} seconds")
        print("-" * 30)
        print(f"{GREEN}✅ Enriched (New): {success_count}{RESET}")
        print(f"{BLUE}📦 Cached (Skipped): {cached_count}{RESET}")
        print(f"{RED}❌ Failed: {failed_count}{RESET}")
        print("=" * 60)
        
        # 4. Final Verification
        total_enriched = db.query(ScholarPaperData).filter(ScholarPaperData.embedding_vector.isnot(None)).count()
        print(f"\n📊 Total papers now with embeddings in DB: {BOLD}{total_enriched}{RESET}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(process_publications())
