"""
Publication Service
Business logic for publication management and PDF processing
"""

import io
import os
import re
from typing import Optional, List, Tuple, Dict
import PyPDF2
import pdfplumber
from sqlalchemy.orm import Session

# Tenacity for API retry logic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log
)

def _is_rate_limit_error(exception):
    """Check if exception is a rate limit error (429 or ResourceExhausted)."""
    error_message = str(exception).lower()
    return (
        '429' in error_message or
        'resource exhausted' in error_message or
        'quota' in error_message or
        'rate limit' in error_message
    )

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(
        f"   ⚠️ Gemini API rate limit hit. Waiting {retry_state.next_action.sleep} seconds before retry {retry_state.attempt_number}/5..."
    ),
    reraise=True
)
def call_gemini_generate_with_retry(model, prompt: str):
    """
    Wrapper for model.generate_content with automatic retry logic.
    Handles rate limits (429) with exponential backoff.
    """
    try:
        return model.generate_content(prompt)
    except Exception as e:
        if _is_rate_limit_error(e):
            print(f"   ⚠️ Rate limit error detected: {str(e)[:100]}")
            raise  # Will trigger retry
        else:
            print(f"   ❌ Non-retryable Gemini API error: {str(e)[:100]}")
            raise


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
    # Normalize text: replace newlines and multiple spaces with single space
    # This helps with PDFs where DOI might be split across lines
    normalized_text = ' '.join(text.split())
    
    # Multiple DOI patterns to try (ordered by specificity)
    patterns = [
        # Pattern 1: Explicit "DOI:" prefix (most reliable)
        r'DOI\s*:?\s*(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)',
        
        # Pattern 2: Standard DOI pattern with word boundary
        r'\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)',
        
        # Pattern 3: DOI in URL format
        r'(?:https?://)?(?:dx\.)?doi\.org/(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            # Extract the DOI part (group 1)
            doi = match.group(1)
            # Clean up any trailing punctuation that might have been captured
            doi = doi.rstrip('.,;)]')
            print(f"   [DOI Extraction] Found DOI: {doi}")
            return f"https://doi.org/{doi}"
    
    print("   [DOI Extraction] No DOI found in text")
    return None


def match_authors_from_text(text: str, db: Session) -> List[int]:
    """
    Match authors from PDF text against researchers in database.
    Searches by ORCID first, then by name variations.
    
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
    
    # ORCID regex pattern (matches XXXX-XXXX-XXXX-XXXX format)
    import re
    orcid_pattern = re.compile(r'\b(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])\b', re.IGNORECASE)
    found_orcids = set(orcid_pattern.findall(text))
    
    for researcher in researchers:
        # Priority 1: Check ORCID match
        if researcher.researcher_details and researcher.researcher_details.orcid:
            orcid = researcher.researcher_details.orcid
            # Clean ORCID (extract just the ID if it's a URL)
            clean_orcid = orcid.split('/')[-1].strip() if '/' in orcid else orcid.strip()
            if clean_orcid in found_orcids:
                matched_ids.append(researcher.id)
                print(f"   [Author Match] ✅ ORCID: {clean_orcid} → {researcher.full_name}")
                continue
        
        # Priority 2: Check full name
        if researcher.full_name and researcher.full_name.lower() in text_lower:
            matched_ids.append(researcher.id)
            print(f"   [Author Match] ✅ Name: {researcher.full_name}")
            continue
        
        # Priority 3: Check researcher details variations
        if researcher.researcher_details:
            details = researcher.researcher_details
            
            # Check first + last name combination
            if details.first_name and details.last_name:
                full_name_variant = f"{details.first_name} {details.last_name}".lower()
                if full_name_variant in text_lower:
                    matched_ids.append(researcher.id)
                    print(f"   [Author Match] ✅ Name variant: {full_name_variant}")
                    continue
            
            # Check name variations (pipe-separated)
            if details.name_variations:
                variations = details.name_variations.split('|')
                for variation in variations:
                    if variation.strip().lower() in text_lower:
                        matched_ids.append(researcher.id)
                        print(f"   [Author Match] ✅ Variation: {variation.strip()}")
                        break
    
    return list(set(matched_ids))  # Remove duplicates


def analyze_text_with_ai(text: str, api_key: Optional[str] = None) -> Dict:
    """
    Analyze text with AI to generate summaries and extract journal metadata.
    Returns a dictionary with summaries and journal analysis.
    """
    try:
        import google.generativeai as genai
        import json
        
        # Get API key
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
            print("!!! [AI DEBUG] Warning: GOOGLE_API_KEY not found in environment")
            return {
                "summary_es": "Error: API Key no encontrada",
                "summary_en": "Error: API Key not found",
                "journal_analysis": None
            }
        
        print(f"!!! [AI DEBUG] Starting analysis with model {os.environ.get('GEMINI_MODEL_NAME', 'default')}...")
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
        model = genai.GenerativeModel(model_name)
        
        # Prepare prompt (use first 15000 chars)
        text_sample = text[:15000]
        prompt = f"""Analiza este texto de una publicación científica.

TAREAS:
1. Generar resumen en ESPAÑOL (max 150 palabras)
2. Generar resumen en INGLÉS (max 150 words)
3. EXTRAER SOLO EL NOMBRE DE LA REVISTA donde se publicó
4. EXTRAER TÍTULO EXACTO DEL PAPER

IMPORTANTE: 
- NO busques métricas (JIF, SJR, cuartiles, etc.) - eso se hará después manualmente.
- Solo identifica el NOMBRE de la revista.

FORMATO DE RESPUESTA (JSON PURO):
{{
  "title": "Título exacto identificado del paper",
  "summary_es": "Resumen en español...",
  "summary_en": "Summary in english...",
  "journal_analysis": {{
    "journal_name": "Nombre exacto de la Revista",
    "reasoning": "Breve nota de dónde encontré el nombre (ej: header del PDF, metadata)"
  }}
}}

TEXTO:
{text_sample}"""

        # ============== DEBUG LOGGING - EASY TO REMOVE ==============
        print("\n" + "="*80)
        print(f"🤖 [AI PROMPT] Publication Analysis (Summary + Journal)")
        print("="*80)
        print(prompt)
        print("="*80 + "\n")
        # ============================================================

        response = call_gemini_generate_with_retry(model, prompt)
        result_text = response.text
        
        # ============== DEBUG LOGGING - EASY TO REMOVE ==============
        print("\n" + "="*80)
        print(f"✅ [AI RESPONSE] Publication Analysis")
        print("="*80)
        print(result_text)
        print("="*80 + "\n")
        # ============================================================
        
        # Clean markdown formatting if present
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[0].strip()
            
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            print(f"Error parsing AI JSON output: {result_text[:100]}...")
            return {
                "summary_es": "Error generando resumen (Formato inválido)",
                "summary_en": "Error generating summary (Invalid format)",
                "journal_analysis": None
            }
            
    except Exception as e:
        print(f"!!! [AI DEBUG] Critical Error in analyze_text_with_ai: {e}")
        import traceback
        traceback.print_exc()
        return {
            "summary_es": f"Error: {str(e)}",
            "summary_en": f"Error: {str(e)}",
            "journal_analysis": None
        }


def _generate_placeholder_summaries() -> Tuple[str, str]:
    """Generate placeholder summaries when LLM is unavailable."""
    resumen_es = "Resumen en proceso. El contenido se extrajo correctamente pero el resumen automático no está disponible en este momento."
    resumen_en = "Summary in progress. Content was extracted successfully but automatic summary is not available at this time."
    return resumen_es, resumen_en


def enrich_publication_data(file_bytes: bytes, filename: str, db: Session, skip_ai: bool = False) -> dict:
    """
    Orchestrator function that extracts and enriches all data from a PDF.
    
    Args:
        file_bytes: PDF file as bytes
        filename: Original filename
        db: Database session
        skip_ai: If True, skips LLM summary generation (Fast Path)
        
    Returns:
        Dictionary with enriched publication data
    """
    # Extract text
    text = extract_text_from_pdf(file_bytes)
    
    # Prepare result
    result = {
        "filename": filename,
        "text": text,
        "doi": None,  # Clean DOI string
        "doi_url": None,  # Full https://doi.org/... URL
        "matched_author_ids": [],
        "resumen_es": "",
        "resumen_en": "",
        "ai_extracted_title": None,  # New field
        "processing_notes": []
    }
    
    # Detect DOI
    if text:
        doi_url = extract_doi(text)
        if doi_url:
            result["doi_url"] = doi_url
            # Extract clean DOI (e.g., "10.1234/abc" from "https://doi.org/10.1234/abc")
            clean_doi = doi_url.split("doi.org/")[-1] if "doi.org/" in doi_url else doi_url.replace("https://doi.org/", "")
            result["doi"] = clean_doi
            result["processing_notes"].append(f"DOI detectado: {doi_url}")
        else:
            result["doi"] = None
            result["processing_notes"].append("No se encontró DOI en el documento")
    
    # Extract ORCIDs
    extracted_orcids = []
    if text:
        import re
        orcid_pattern = re.compile(r'\b(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])\b', re.IGNORECASE)
        found_orcids = set(orcid_pattern.findall(text))
        if found_orcids:
            extracted_orcids = list(found_orcids)
            result["extracted_orcids"] = ",".join(extracted_orcids)
            result["processing_notes"].append(f"{len(extracted_orcids)} ORCID(s) detectado(s): {', '.join(extracted_orcids)}")
    
    # Match authors
    if text:
        matched_ids = match_authors_from_text(text, db)
        result["matched_author_ids"] = matched_ids
        if matched_ids:
            result["processing_notes"].append(f"{len(matched_ids)} autor(es) detectado(s) en la base de datos")
        else:
            result["processing_notes"].append("No se detectaron autores conocidos")
    
    # Generate summaries and analysis
    if not skip_ai and text and len(text) > 100:  # Only if there's meaningful content
        analysis = analyze_text_with_ai(text)
        result["resumen_es"] = analysis.get("summary_es")
        result["resumen_en"] = analysis.get("summary_en")
        result["ai_journal_analysis"] = analysis.get("journal_analysis")
        result["ai_extracted_title"] = analysis.get("title") # Capture title
        result["processing_notes"].append("Análisis IA completado (Resumen + Journal + Título)")
    else:
        placeholders = _generate_placeholder_summaries()
        result["resumen_es"] = placeholders[0]
        result["resumen_en"] = placeholders[1]
        result["ai_journal_analysis"] = None
        
        if skip_ai:
            result["processing_notes"].append("Resumen IA omitido por usuario (Fast Path)")
        else:
            result["processing_notes"].append("Texto insuficiente para generar resumen")

    # FALLBACK: If DOI is still missing, try to search in OpenAlex by Title
    if not result["doi"]:
        from services import openalex_service
        
        search_title = result.get("ai_extracted_title")
        
        # Fallback to filename if AI didn't provide title
        if not search_title:
             # Heuristic clean filename
             clean_name = filename.replace('.pdf', '').replace('_', ' ')
             # Remove common prefixes like '2024- ', '24- '
             import re
             clean_name = re.sub(r'^\d{2,4}[-_]\s*', '', clean_name)
             search_title = clean_name
        
        if search_title and len(search_title) > 5:
            result["processing_notes"].append(f"Intentando buscar DOI por título: {search_title[:50]}...")
            match = openalex_service.search_publication_by_title(search_title)
            
            if match and match.get("doi"):
                doi_url = match.get("doi")
                # Clean DOI
                clean_doi = doi_url.split("doi.org/")[-1] if "doi.org/" in doi_url else doi_url.replace("https://doi.org/", "")
                
                result["doi"] = clean_doi
                result["doi_url"] = doi_url
                # We could also use match['title'] to correct the title later?
                # But ingestion_service handles metadata fetching.
                result["processing_notes"].append(f"✅ DOI encontrado en OpenAlex: {clean_doi}")
            else:
                result["processing_notes"].append("❌ No se encontró DOI en OpenAlex por título")
    
    return result


def generate_summary_from_text(text: str) -> Tuple[str, str]:
    """
    Generate Spanish and English summaries from text using Gemini.
    """
    import os
    import re
    import google.generativeai as genai
    
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise Exception("Google API Key not found")
        
    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
    model = genai.GenerativeModel(model_name)
    
    # Use reasonable sample size
    text_sample = text[:8000]
    
    prompt = f"""Resume este artículo científico en 150 palabras o menos.

Proporciona DOS resúmenes del mismo contenido:
1. Primero en ESPAÑOL
2. Luego en INGLÉS

Formato de respuesta:
[ES] <resumen en español>
[EN] <summary in English>

Texto del artículo:
{text_sample}"""

    response = call_gemini_generate_with_retry(model, prompt)
    result_text = response.text
    
    resumen_es = ""
    resumen_en = ""
        
    es_match = re.search(r'\[ES\]\s*(.+?)(?=\[EN\]|$)', result_text, re.DOTALL | re.IGNORECASE)
    if es_match:
        resumen_es = es_match.group(1).strip()
    
    en_match = re.search(r'\[EN\]\s*(.+?)$', result_text, re.DOTALL | re.IGNORECASE)
    if en_match:
         resumen_en = en_match.group(1).strip()
         
    if not resumen_es and not resumen_en:
         resumen_es = result_text
         
    return resumen_es, resumen_en


def generate_summaries_only(text: str) -> dict:
    """
    FASE 2 (SIMPLIFICADA): Genera SOLO resúmenes ES/EN.
    
    NO busca métricas de revista (eso se hace en FASE 3 con Google Search).
    Modelo rápido sin grounding.
    
    Args:
        text: Contenido extraído del PDF
        
    Returns:
        dict con keys: summary_es, summary_en
    """
    import json
    import google.generativeai as genai
    
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("WARNING: GOOGLE_API_KEY not found")
        return {
            "summary_es": "API Key no configurada",
            "summary_en": "API Key not configured"
        }
    
    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
    model = genai.GenerativeModel(model_name)
    
    # Limitar texto para no exceder límites de tokens
    text_sample = text[:50000] if len(text) > 50000 else text
    
    prompt = f"""Analiza este texto de una publicación científica y genera dos resúmenes:

1. Resumen en ESPAÑOL (máximo 150 palabras):
   - Objetivo del estudio
   - Metodología principal
   - Resultados clave
   - Conclusión

2. Summary in ENGLISH (maximum 150 words):
   - Study objective
   - Main methodology
   - Key results
   - Conclusion

IMPORTANTE:
- Solo genera resúmenes, NO extraigas nombre de revista ni métricas
- Devuelve ÚNICAMENTE un JSON válido

FORMATO:
{{
  "summary_es": "Resumen en español aquí...",
  "summary_en": "Summary in english here..."
}}

TEXTO:
{text_sample}
"""
    
    print(f"   [AI] Generating summaries with {model_name}...")
    
    try:
        response = call_gemini_generate_with_retry(model, prompt)
        result_text = response.text
        
        # Limpiar markdown si está presente
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        # Parsear JSON
        try:
            data = json.loads(result_text)
            return {
                "summary_es": data.get("summary_es", ""),
                "summary_en": data.get("summary_en", "")
            }
        except json.JSONDecodeError as e:
            print(f"   [AI] JSON parse error: {str(e)}")
            print(f"   [AI] Response preview: {result_text[:200]}...")
            
            # Fallback: intentar extraer texto plano
            return {
                "summary_es": result_text[:500] if result_text else "Error generando resumen",
                "summary_en": "Error generating summary"
            }
            
    except Exception as e:
        print(f"   [AI] Error: {str(e)}")
        raise
