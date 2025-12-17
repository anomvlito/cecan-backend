"""
Publication Service
Business logic for publication management and PDF processing
"""

import io
import os
import re
from typing import Optional, List, Tuple
import PyPDF2
import pdfplumber
from sqlalchemy.orm import Session


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Extracted text as a string. Empty string if extraction fails.
    """
    text_content = []
    
    # Try with pdfplumber first (better for complex layouts)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
        
        if text_content:
            return "\n\n".join(text_content)
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}")
    
    # Fallback to PyPDF2
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
        
        return "\n\n".join(text_content)
    except Exception as e:
        print(f"PyPDF2 extraction failed: {e}")
        return ""


def validate_pdf_file(filename: str, content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate that a file is a proper PDF.
    
    Args:
        filename: Name of the file
        content: File content as bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check extension
    if not filename.lower().endswith('.pdf'):
        return False, "El archivo debe ser un PDF (.pdf)"
    
    # Check PDF magic number
    if not content.startswith(b'%PDF'):
        return False, "El archivo no es un PDF válido"
    
    # Check minimum size (avoid empty files)
    if len(content) < 100:
        return False, "El archivo PDF está vacío o corrupto"
    
    return True, None


def extract_doi(text: str) -> Optional[str]:
    """
    Extract DOI from PDF text using regex pattern.
    
    Args:
        text: Full text content from PDF
        
    Returns:
        DOI URL (with https://doi.org/ prefix) or None if not found
    """
    # DOI regex pattern (case-insensitive)
    # Matches standard DOI format: 10.xxxx/...
    doi_pattern = r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b'
    
    # Search in first 5000 characters (typically front matter)
    search_text = text[:5000]
    
    match = re.search(doi_pattern, search_text, re.IGNORECASE)
    if match:
        doi = match.group(1)
        return f"https://doi.org/{doi}"
    
    return None


def match_authors_from_text(text: str, db: Session) -> List[int]:
    """
    Match authors from PDF text against researchers in database.
    
    Args:
        text: Full text content from PDF
        db: Database session
        
    Returns:
        List of member IDs that were found in the text
    """
    from core.models import AcademicMember, ResearcherDetails
    
    # Get all active researchers
    researchers = db.query(AcademicMember).filter(
        AcademicMember.member_type == 'researcher',
        AcademicMember.is_active == True
    ).all()
    
    matched_ids = []
    text_lower = text.lower()
    
    for researcher in researchers:
        # Check full name
        if researcher.full_name and researcher.full_name.lower() in text_lower:
            matched_ids.append(researcher.id)
            continue
        
        # Check researcher details if available
        if researcher.researcher_details:
            details = researcher.researcher_details
            
            # Check first + last name combination
            if details.first_name and details.last_name:
                full_name_variant = f"{details.first_name} {details.last_name}".lower()
                if full_name_variant in text_lower:
                    matched_ids.append(researcher.id)
                    continue
            
            # Check name variations (pipe-separated)
            if details.name_variations:
                variations = details.name_variations.split('|')
                for variation in variations:
                    if variation.strip().lower() in text_lower:
                        matched_ids.append(researcher.id)
                        break
    
    return list(set(matched_ids))  # Remove duplicates


def generate_summary_with_llm(text: str, api_key: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate Spanish and English summaries using Google Gemini LLM.
    
    Args:
        text: Full text content from PDF
        api_key: Google API key (optional, will use env var if not provided)
        
    Returns:
        Tuple of (resumen_es, resumen_en)
    """
    try:
        import google.generativeai as genai
        
        # Get API key
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
            print("Warning: GOOGLE_API_KEY not found. Using placeholder summaries.")
            return _generate_placeholder_summaries()
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
        model = genai.GenerativeModel(model_name)
        
        # Prepare prompt (use first 3000 chars to avoid token limits)
        text_sample = text[:3000]
        prompt = f"""Resume este artículo científico en 150 palabras o menos.

Proporciona DOS resúmenes del mismo contenido:
1. Primero en ESPAÑOL
2. Luego en INGLÉS

Formato de respuesta:
[ES] <resumen en español>
[EN] <summary in English>

Texto del artículo:
{text_sample}"""
        
        # Generate summary
        response = model.generate_content(prompt)
        result_text = response.text
        
        # Parse response
        resumen_es = ""
        resumen_en = ""
        
        # Extract Spanish summary
        es_match = re.search(r'\[ES\]\s*(.+?)(?=\[EN\]|$)', result_text, re.DOTALL | re.IGNORECASE)
        if es_match:
            resumen_es = es_match.group(1).strip()
        
        # Extract English summary
        en_match = re.search(r'\[EN\]\s*(.+?)$', result_text, re.DOTALL | re.IGNORECASE)
        if en_match:
            resumen_en = en_match.group(1).strip()
        
        # Fallback if parsing failed
        if not resumen_es or not resumen_en:
            return _generate_placeholder_summaries()
        
        return resumen_es, resumen_en
        
    except Exception as e:
        print(f"Error generating summary with LLM: {e}")
        return _generate_placeholder_summaries()


def _generate_placeholder_summaries() -> Tuple[str, str]:
    """Generate placeholder summaries when LLM is unavailable."""
    resumen_es = "Resumen en proceso. El contenido se extrajo correctamente pero el resumen automático no está disponible en este momento."
    resumen_en = "Summary in progress. Content was extracted successfully but automatic summary is not available at this time."
    return resumen_es, resumen_en


def enrich_publication_data(file_bytes: bytes, filename: str, db: Session) -> dict:
    """
    Orchestrator function that extracts and enriches all data from a PDF.
    
    Args:
        file_bytes: PDF file as bytes
        filename: Original filename
        db: Database session
        
    Returns:
        Dictionary with enriched publication data
    """
    # Extract text
    text = extract_text_from_pdf(file_bytes)
    
    # Prepare result
    result = {
        "filename": filename,
        "text": text,
        "doi_url": None,
        "matched_author_ids": [],
        "resumen_es": "",
        "resumen_en": "",
        "processing_notes": []
    }
    
    # Detect DOI
    if text:
        doi_url = extract_doi(text)
        if doi_url:
            result["doi_url"] = doi_url
            result["processing_notes"].append(f"DOI detectado: {doi_url}")
        else:
            result["processing_notes"].append("No se encontró DOI en el documento")
    
    # Match authors
    if text:
        matched_ids = match_authors_from_text(text, db)
        result["matched_author_ids"] = matched_ids
        if matched_ids:
            result["processing_notes"].append(f"{len(matched_ids)} autor(es) detectado(s) en la base de datos")
        else:
            result["processing_notes"].append("No se detectaron autores conocidos")
    
    # Generate summaries
    if text and len(text) > 100:  # Only if there's meaningful content
        resumen_es, resumen_en = generate_summary_with_llm(text)
        result["resumen_es"] = resumen_es
        result["resumen_en"] = resumen_en
        result["processing_notes"].append("Resúmenes generados exitosamente")
    else:
        result["resumen_es"], result["resumen_en"] = _generate_placeholder_summaries()
        result["processing_notes"].append("Texto insuficiente para generar resumen")
    
    return result
