import requests
from bs4 import BeautifulSoup

import sqlite3
import time
import random
import json
import sys
import os
from pydantic import BaseModel
from typing import Optional, List
from pypdf import PdfReader

# Add parent directory to path to import backend modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

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
        
        # Based on the user's image and typical WordPress structures
        # We need to find the articles. 
        # Looking at the provided text dump, it seems to be a list.
        # Let's assume a standard article or div structure.
        # We will look for elements that contain "Ver detalles" or "Descargar"
        
        # Strategy: Find all "Descargar" links, then find the parent container to get the title and date.
        
        download_buttons = soup.find_all('a', string=lambda t: t and "Descargar" in t)
        
        for btn in download_buttons:
            try:
                # The structure seems to be: 
                # Container -> Date
                #           -> Title
                #           -> Buttons (Details, Download)
                
                # Let's traverse up to find the container
                # Usually the button is in a div, which is in the main article container
                container = btn.find_parent('article') or btn.find_parent('div', class_='publication-item') # Hypothetical class
                
                # If we can't find a specific container, let's try to find the closest header
                if not container:
                    # Fallback: Go up 2-3 levels
                    container = btn.parent.parent
                
                # Extract Title
                title_tag = container.find('h3') or container.find('h4') or container.find('h2')
                if not title_tag:
                    # Try finding previous sibling elements if structure is flat
                    pass
                
                title = title_tag.get_text(strip=True) if title_tag else "Sin título"
                
                # Extract Date
                date_tag = container.find('span', class_='date') or container.find('time')
                # If not found, try to find a date pattern in the text
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                # Extract PDF URL
                pdf_url = btn.get('href')
                
                if title and pdf_url:
                    publications.append({
                        "titulo": title,
                        "fecha": date,
                        "url_origen": pdf_url,
                        "categoria": "Científica"
                    })
            except Exception as e:
                print(f"Error parsing publication item: {e}")
                continue
                
        # If the above specific strategy fails, let's try a more generic one based on the screenshot
        if not publications:
            print("Specific strategy failed, trying generic iteration...")
            # The screenshot shows items with a date, title, and buttons.
            # Let's iterate over all 'article' tags or divs with specific classes if we knew them.
            # Since we don't know the class, let's look for the visual structure.
            
            # Find all elements that look like titles (e.g., h3)
            # and check if they have a download link nearby.
            potential_titles = soup.find_all(['h3', 'h4'])
            for t in potential_titles:
                link = t.find_next('a', href=True)
                # Check if this link or the next one is a download link
                # In the screenshot, "Descargar" is a button.
                
                # Look for "Descargar" in the next few elements
                next_elems = t.find_all_next('a', limit=5)
                pdf_url = None
                for a in next_elems:
                    if "Descargar" in a.get_text() or "download" in a.get('class', []):
                        pdf_url = a.get('href')
                        break
                
                if pdf_url:
                    # Found a match
                    # Date is usually before the title
                    prev = t.find_previous(text=True).strip()
                    date = prev if len(prev) < 20 else "" # Simple heuristic
                    
                    publications.append({
                        "titulo": t.get_text(strip=True),
                        "fecha": date,
                        "url_origen": pdf_url,
                        "categoria": "Científica"
                    })

        print(f"Found {len(publications)} publications.")
        return publications

    except Exception as e:
        print(f"Error scraping CECAN publications: {e}")
        return []

def scrape_uc_staff():
    """
    Scrapes the UC Medicine research directory for staff information.
    Returns a dictionary keyed by normalized name with data: {cargo, url_foto}
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

            parent = img.find_parent('a')
            container = parent.parent if parent else img.parent
            
            text = container.get_text(separator='\n').strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            cargo = "Investigador"
            possible_titles = []
            
            for line in lines:
                if line.lower() == name.lower():
                    continue
                if len(line) > 3 and line != name:
                    possible_titles.append(line)
            
            if possible_titles:
                cargo = ", ".join(possible_titles[:2]) 
                
            norm_name = normalize_name(name)
            if norm_name:
                staff_data[norm_name] = {
                    "cargo_oficial": cargo,
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, full_name FROM academic_members WHERE member_type='researcher'")
    investigators = cursor.fetchall()
    
    for inv_id, name in investigators:
        print(f"Processing {name}...")
        
        # Update UC Data if available
        norm_name = normalize_name(name)
        if norm_name and norm_name in uc_data:
            data = uc_data[norm_name]
            
            # Check if details exist
            cursor.execute("SELECT id FROM researcher_details WHERE member_id = ?", (inv_id,))
            details_exists = cursor.fetchone()
            
            if details_exists:
                cursor.execute("""
                    UPDATE researcher_details 
                    SET url_foto = ?
                    WHERE member_id = ?
                """, (data['url_foto'], inv_id))
            else:
                cursor.execute("""
                    INSERT INTO researcher_details (member_id, url_foto)
                    VALUES (?, ?)
                """, (inv_id, data['url_foto']))
            
            conn.commit()
            
    conn.close()
    print("Staff synchronization complete.")

def sync_publications_data():
    """
    Orchestrates the scraping and DB update for publications.
    """
    print("Starting publications synchronization...")
    
    pubs = scrape_cecan_publications()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for pub in pubs:
        print(f"Processing publication: {pub['titulo']}")
        
        # Check if exists
        cursor.execute("SELECT id FROM publicaciones WHERE titulo = ?", (pub['titulo'],))
        exists = cursor.fetchone()
        
        if exists:
            print("Skipping existing publication.")
            continue
            
        # Download PDF
        filename = f"{int(time.time())}_{random.randint(1000,9999)}.pdf"
        pdf_path = download_pdf(pub['url_origen'], filename)
        
        content_text = ""
        local_path = ""
        
        if pdf_path:
            local_path = pdf_path
            print("Extracting text...")
            content_text = extract_text_from_pdf(pdf_path)
            
        cursor.execute("""
            INSERT INTO publicaciones (
                titulo, fecha, url_origen, path_pdf_local, contenido_texto, categoria,
                has_valid_affiliation, has_funding_ack, anid_report_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pub['titulo'], 
            pub['fecha'], 
            pub['url_origen'], 
            local_path, 
            content_text,
            pub['categoria'],
            False,  # has_valid_affiliation - will be audited later
            False,  # has_funding_ack - will be audited later
            'Error'  # anid_report_status - default value
        ))
        conn.commit()
        
    conn.close()
    print("Publications synchronization complete.")

if __name__ == "__main__":
    # sync_staff_data()
    sync_publications_data()
