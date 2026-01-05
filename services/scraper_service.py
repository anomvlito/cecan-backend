import requests
from bs4 import BeautifulSoup
import time
import random
import json
import sys
import os
from typing import Optional, List, Dict, Any
from pypdf import PdfReader
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)
from sqlalchemy.orm import Session

# Add parent directory to path to import backend modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH
from database.session import SessionLocal
from core.models import Publication, AcademicMember, ResearcherDetails

# Get the project root directory (parent of backend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "docs", "pdfs")
os.makedirs(DATA_DIR, exist_ok=True)


def normalize_name(name):
    if not name:
        return None
    return name.strip().replace('  ', ' ')

def download_pdf(url, filename):
    """Downloads a PDF from a URL and saves it to the data directory."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath
    except Exception as e:
        print(f"Error downloading PDF {url}: {e}")
        return None

def extract_text_from_pdf(filepath):
    """Extracts text content from a PDF file."""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from {filepath}: {e}")
        return ""

def scrape_cecan_publications():
    """
    Scrapes publications from the CECAN website.
    """
    print("Scraping CECAN publications...")
    url = "https://cecan.cl/publicaciones/?cat=cientificas"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        publications = []
        
        # Based on existing strategy
        download_buttons = soup.find_all('a', string=lambda t: t and "Descargar" in t)
        
        for btn in download_buttons:
            try:
                container = btn.find_parent('article') or btn.find_parent('div', class_='publication-item')
                if not container:
                    container = btn.parent.parent
                
                title_tag = container.find('h3') or container.find('h4') or container.find('h2')
                
                title = title_tag.get_text(strip=True) if title_tag else "Sin título"
                
                date_tag = container.find('span', class_='date') or container.find('time')
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                pdf_url = btn.get('href')
                
                if title and pdf_url:
                    publications.append({
                        "title": title, # Renamed from titulo
                        "year": date,   # Renamed from fecha
                        "url": pdf_url, # Renamed from url_origen
                        "category": "Científica" # Renamed from categoria
                    })
            except Exception as e:
                print(f"Error parsing publication item: {e}")
                continue
                
        # Generic strategy fallback
        if not publications:
            print("Specific strategy failed, trying generic iteration...")
            potential_titles = soup.find_all(['h3', 'h4'])
            for t in potential_titles:
                link = t.find_next('a', href=True)
                next_elems = t.find_all_next('a', limit=5)
                pdf_url = None
                for a in next_elems:
                    if "Descargar" in a.get_text() or "download" in a.get('class', []):
                        pdf_url = a.get('href')
                        break
                
                if pdf_url:
                    prev = t.find_previous(text=True).strip()
                    date = prev if len(prev) < 20 else ""
                    
                    publications.append({
                        "title": t.get_text(strip=True), # Renamed from titulo
                        "year": date, # Renamed from fecha
                        "url": pdf_url, # Renamed from url_origen
                        "category": "Científica" # Renamed from categoria
                    })

        print(f"Found {len(publications)} publications.")
        return publications

    except Exception as e:
        print(f"Error scraping CECAN publications: {e}")
        return []

def scrape_uc_staff():
    """
    Scrapes the UC Medicine research directory for staff information.
    """
    print("Scraping UC Medicine staff...")
    url = "https://medicina.uc.cl/investigacion/direccion-de-investigacion/investigadores/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        staff_data = {}
        
        images = soup.find_all('img')
        for img in images:
            name = img.get('alt', '').strip()
            src = img.get('src', '')
            
            if not name or len(name) < 5:
                continue
            if 'logo' in src.lower() or 'icon' in src.lower():
                continue
            if not (name.startswith('Dr') or name.startswith('Prof') or name.startswith('Marcela') or ' ' in name):
                 continue

            norm_name = normalize_name(name)
            if norm_name:
                staff_data[norm_name] = {
                    "url_foto": src
                }
                
        print(f"Found {len(staff_data)} researchers.")
        return staff_data

    except Exception as e:
        print(f"Error scraping UC staff: {e}")
        return {}

def sync_staff_data():
    """
    Orchestrates the scraping and DB update for staff.
    """
    print("Starting staff synchronization...")
    
    uc_data = scrape_uc_staff()
    
    db = SessionLocal()
    try:
        investigators = db.query(AcademicMember).filter(AcademicMember.member_type == 'researcher').all()
        
        for inv in investigators:
            print(f"Processing {inv.full_name}...")
            
            norm_name = normalize_name(inv.full_name)
            if norm_name and norm_name in uc_data:
                data = uc_data[norm_name]
                
                # Check or create details
                if not inv.researcher_details:
                    inv.researcher_details = ResearcherDetails(member_id=inv.id)
                
                inv.researcher_details.url_foto = data['url_foto']
                db.add(inv) # Mark as modified
                
        db.commit()
    finally:
        db.close()
        
    print("Staff synchronization complete.")

def sync_publications_data():
    """
    Orchestrates the scraping and DB update for publications.
    """
    print("Starting publications synchronization...")
    
    pubs = scrape_cecan_publications()
    
    db = SessionLocal()
    try:
        for pub in pubs:
            print(f"Processing publication: {pub['title']}")
            
            # Check by title
            exists = db.query(Publication).filter(Publication.title == pub['title']).first()
            if exists:
                print("Skipping existing publication.")
                continue
                
            # Download PDF
            filename = f"{int(time.time())}_{random.randint(1000,9999)}.pdf"
            pdf_path = download_pdf(pub['url'], filename)
            
            content_text = ""
            local_path = ""
            
            if pdf_path:
                local_path = pdf_path
                print("Extracting text...")
                content_text = extract_text_from_pdf(pdf_path)
                
            new_pub = Publication(
                title=pub['title'], 
                year=pub['year'], 
                url=pub['url'], 
                local_path=local_path, 
                content=content_text,
                category=pub['category'],
                has_valid_affiliation=False,
                has_funding_ack=False,
                anid_report_status='Pending'
            )
            db.add(new_pub)
            db.commit()
            
    except Exception as e:
        db.rollback()
        print(f"Error syncing publications: {e}")
    finally:
        db.close()

    print("Publications synchronization complete.")

def _is_rate_limit_error(exception):
    """Check if exception is a rate limit error (429)."""
    if isinstance(exception, requests.exceptions.HTTPError):
        return exception.response.status_code == 429
    return False

@retry(
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry_error_callback=lambda retry_state: {}, # Return empty dict on final failure
    reraise=False
)
def get_openalex_metrics(orcid: Optional[str] = None, doi: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch metrics from OpenAlex API.
    """
    base_url = "https://api.openalex.org"
    params = {"mailto": "admin@cecan.cl"} # OpenAlex polite pool
    
    try:
        if doi:
            # Format DOI: remove url prefix if present
            clean_doi = doi.split('doi.org/')[-1]
            url = f"{base_url}/works/https://doi.org/{clean_doi}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "citation_count": data.get("cited_by_count", 0),
                "source": "openalex"
            }
            
        elif orcid:
            # Format ORCID: ensure it's just the ID or full URL
            clean_orcid = orcid.split('orcid.org/')[-1]
            url = f"{base_url}/authors/https://orcid.org/{clean_orcid}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "h_index": data.get("summary_stats", {}).get("h_index", 0),
                "citation_count": data.get("cited_by_count", 0),
                "i10_index": data.get("summary_stats", {}).get("i10_index", 0),
                "source": "openalex"
            }
    except Exception as e:
        if _is_rate_limit_error(e):
            raise # Trigger tenacity retry
        print(f"Error fetching from OpenAlex: {e}")
    return {}

@retry(
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry_error_callback=lambda retry_state: {},
    reraise=False
)
def get_semantic_scholar_metrics(doi: str) -> Dict[str, Any]:
    """
    Fetch metrics from Semantic Scholar API using DOI.
    """
    base_url = "https://api.semanticscholar.org/graph/v1"
    clean_doi = doi.split('doi.org/')[-1]
    url = f"{base_url}/work/DOI:{clean_doi}"
    params = {"fields": "citationCount,influentialCitationCount"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "citation_count": data.get("citationCount", 0),
            "influential_citations": data.get("influentialCitationCount", 0),
            "source": "semanticscholar"
        }
    except Exception as e:
        if _is_rate_limit_error(e):
            raise
        print(f"Error fetching from Semantic Scholar: {e}")
    return {}

if __name__ == "__main__":
    # sync_staff_data()
    sync_publications_data()
