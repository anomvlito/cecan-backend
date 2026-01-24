
import os
import sys
import io
import pdfplumber
import PyPDF2

# Mock the extraction function from publication_service.py
def extract_text_debug(file_path):
    print(f"\n{'='*50}")
    print(f"DEBUGGING: {os.path.basename(file_path)}")
    print(f"{'='*50}")
    
    text_content = []
    
    try:
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
            
        # Try with pdfplumber (layout=True)
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                # Just check first page for the DOI check
                first_page = pdf.pages[0]
                text = first_page.extract_text(layout=True)
                if text:
                    print("--- METHOD: pdfplumber (layout=True) ---")
                    print(text[:2000]) # First 2000 chars
                    return
        except Exception as e:
            print(f"pdfplumber failed: {e}")

        # Fallback to PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            page = pdf_reader.pages[0]
            text = page.extract_text()
            print("--- METHOD: PyPDF2 ---")
            print(text[:2000])
        except Exception as e:
            print(f"PyPDF2 failed: {e}")

    except Exception as e:
        print(f"File read failed: {e}")

# Files identified by user
files_to_check = [
    "11-_gutjnl-2023-331059.pdf",
    "65-_Challenges_of_updating_JA_(2025).pdf", 
    "64-_The_evolution_of_serious_health-related_suffering_PPerez_(2025).pdf",
    "58-_OLGA_and_OLGIM_(2025).pdf"
]

# Use relative path since we are running from cecan-backend
base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "publications")

for filename in files_to_check:
    full_path = os.path.join(base_path, filename)
    if os.path.exists(full_path):
        extract_text_debug(full_path)
    else:
        print(f"\nFILE NOT FOUND: {filename}")
        # Try to fuzzy find
        for f in os.listdir(base_path):
            if filename[:10] in f:
                print(f"  Did you mean: {f}?")
                extract_text_debug(os.path.join(base_path, f))
