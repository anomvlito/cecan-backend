"""
AI Analysis Routes - Journal Analysis with Gemini and Data Triangulation
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any
import os

from database.session import get_db
from core.models import WosJournalMirror
from .journals import search_wos_mirror

router = APIRouter(tags=["External Metrics"])


# --- AI JOURNAL ANALYSIS (STATELESS) ---

JOURNAL_METRICS_PROMPT_TEMPLATE = """Actúa como un experto en bibliometría.
⚠️ INSTRUCCIÓN CRÍTICA: DEBES USAR LA HERRAMIENTA DE BÚSQUEDA DE GOOGLE (Google Search).
NO uses tu conocimiento interno pre-entrenado. Busca en internet los datos AHORA MISMO.

Objetivo: Buscar el JIF (Impact Factor) y Cuartiles más recientes (2024 o 202) para:
Revista: {journal_name}
Editorial: {publisher}

Reporte requerido (JSON):
1. **JIF más reciente**: Busca explícitamente "Journal Impact Factor {journal_name} 2024" o "2025".
   - Si encuentras el JIF Released en Junio 2024 (que corresponde a datos 2023), úsalo pero acláralo.
   - Si encuentras JIF 2024 real (publicado en 2025), mejor.
2. **Categorías**: Las 5 principales. Prioriza WOS (JCR). Si no, Scopus (SJR).

NO INVENTES DATOS. Si no encuentras el dato exacto 2024, di "N/A".

--- FORMATO JSON EXACTO ---
{{
  "jif_current": 2.6,
  "jif_year": 2023,
  "jif_5year": 3.2,
  "scopus_sjr": 0.803,
  "scopus_snip": 1.065,
  "categories": [
    {{
      "category_name": "Multidisciplinary Sciences",
      "quartile": "Q1",
      "percentile": 67.4,
      "ranking": "48/134",
      "source": "WOS"
    }}
  ],
  "reasoning": "Busqué en Google y encontré el JCR 2023 released en Junio 2024 en [fuente]."
}}
"""

@router.post("/analyze-journal-ai")
async def analyze_journal_ai(
    payload: Dict[str, str] = Body(..., examples=[{"journal_name": "Nature", "publisher": "Springer"}])
) -> Dict[str, Any]:
    """
    Stateless endpoint to analyze a journal using Gemini with Google Search Grounding.
    Does not require the journal to exist in the database.
    """
    import google.generativeai as genai
    from google.generativeai import types
    import json

    journal_name = payload.get("journal_name", "Unknown")
    publisher = payload.get("publisher", "Unknown")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Google API Key not configured")

    # Usamos gemini-1.5-flash para balancear velocidad/costo (Free Tier incluye 1500 queries/dia)
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash")

    prompt = JOURNAL_METRICS_PROMPT_TEMPLATE.format(
        journal_name=journal_name,
        publisher=publisher
    )

    try:
        # INTENTO 1: Con GROUNDING (Calidad Premium "Google Search")
        # Sintaxis validada: {'google_search': {}}
        tools = [{'google_search': {}}]

        model_grounded = genai.GenerativeModel(
            model_name=model_name,
            tools=tools
        )

        # print(f"🤖 [AI-Ext] Intentando con Grounding...")

        response = model_grounded.generate_content(
            prompt,
            generation_config=types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
                response_mime_type="application/json"
            )
        )

    except Exception as e_grounding:
        # FALLBACK: Si falla el Grounding (API Error 400, Cuota, etc), usar modelo base
        print(f"⚠️ [AI-Ext] Falló Grounding ({e_grounding}). Usando Fallback sin búsqueda.")

        model_fallback = genai.GenerativeModel(model_name=model_name) # Sin tools

        response = model_fallback.generate_content(
            prompt, # Reusamos el mismo prompt
            generation_config=types.GenerationConfig(
                temperature=0.1, # Un poco más creativo para compensar falta de datos
                max_output_tokens=2048,
                response_mime_type="application/json"
            )
        )

    # Procesamiento común de la respuesta (sea Grounded o Fallback)
    try:
        result_text = response.text

        # Clean markdown
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[0].strip()

        data = json.loads(result_text)

        # Agregar metadata de grounding si existe (Solo vendrá del Intento 1)
        grounding_urls = []
        if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
             for chunk in response.grounding_metadata.grounding_chunks:
                if hasattr(chunk, 'web'):
                    grounding_urls.append(chunk.web.uri)

        data["grounding_urls"] = grounding_urls[:5] # Top 5 fuentes

        return data

    except Exception as e:
        print(f"❌ [AI-Ext] Error procesando respuesta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triangulate")
async def triangulate_journal_data(
    payload: Dict[str, str] = Body(..., examples=[{"query": "10.1007/s10120-024-01578-3"}], description="Query can be a DOI, Title or ISSN"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    MASTER ENDPOINT for Data Triangulation (Strict Sequential Flow).

    Flow requested by User:
    1. OpenAlex (DOI) -> Get Journal Name & Source ID.
    2. OpenAlex (Source ID) -> Get Exact Publisher (Imperative).
    3. WOS Mirror -> Search by Journal Name (Local DB).
    4. AI Analysis -> Use gathered Context.
    """
    import requests

    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    # Context Variables
    resolved_journal_name = query
    resolved_publisher = "Unknown"
    resolved_issns = []  # New: Store ISSNs for robust searching
    source_id = None
    is_doi = query.startswith("10.") or "doi.org" in query

    status_log = ["Start"]

    # --- STEP 1: OPENALEX DOI LOOKUP (To get Journal Name) ---
    if is_doi:
        clean_doi = query.split('doi.org/')[-1] if 'doi.org/' in query else query
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            r = requests.get(url, params={"mailto": "admin@cecan.cl"}, timeout=10)

            if r.status_code == 200:
                data = r.json()
                primary_loc = data.get("primary_location", {}) or {}
                source = primary_loc.get("source", {}) or {}

                if source.get("display_name"):
                    resolved_journal_name = source.get("display_name")
                    source_id = source.get("id") # OpenAlex ID (e.g., https://openalex.org/S12345)
                    status_log.append(f"Step 1: Resolved DOI to Journal '{resolved_journal_name}' (SourceID: {source_id})")
                else:
                    status_log.append("Step 1: DOI found but no Journal/Source info")
            else:
                 status_log.append(f"Step 1: OpenAlex DOI lookup failed ({r.status_code})")

        except Exception as e:
            print(f"Error Step 1: {e}")
            status_log.append(f"Step 1 Error: {str(e)}")

    # --- STEP 2: OPENALEX SOURCE LOOKUP (Imperative Publisher & ISSNs) ---
    if source_id:
        # Direct lookup by ID
        try:
            s_url = f"https://api.openalex.org/sources/{source_id}"
            r_source = requests.get(s_url, params={"mailto": "admin@cecan.cl"}, timeout=10)
            if r_source.status_code == 200:
                s_data = r_source.json()
                if s_data.get("host_organization_name"):
                    resolved_publisher = s_data.get("host_organization_name")

                # Extract ISSNs for robust matching
                if s_data.get("issn_l"):
                    resolved_issns.append(s_data.get("issn_l"))
                if s_data.get("issn"):
                    resolved_issns.extend(s_data.get("issn"))
                # Remove duplicates
                resolved_issns = list(set(resolved_issns))

                status_log.append(f"Step 2: Resolved Publisher '{resolved_publisher}' and {len(resolved_issns)} ISSNs")
        except Exception as e:
             status_log.append(f"Step 2 Error (ID lookup): {e}")

    elif not is_doi:
        # If it wasn't a DOI, we need to search for the journal in OpenAlex to get the publisher
        try:
             # Search sources by name
             search_url = "https://api.openalex.org/sources"
             params = {"search": resolved_journal_name, "filter": "type:journal", "per_page": 1}
             r_search = requests.get(search_url, params=params, timeout=10)
             if r_search.status_code == 200:
                 res = r_search.json().get("results", [])
                 if res:
                     top_match = res[0]
                     resolved_journal_name = top_match.get("display_name", resolved_journal_name) # Refine name
                     resolved_publisher = top_match.get("host_organization_name", "Unknown")

                     # Extract ISSNs
                     if top_match.get("issn_l"):
                         resolved_issns.append(top_match.get("issn_l"))
                     if top_match.get("issn"):
                         resolved_issns.extend(top_match.get("issn"))
                     resolved_issns = list(set(resolved_issns))

                     status_log.append(f"Step 2: Searched Journal, found Publisher '{resolved_publisher}'")
        except Exception as e:
             status_log.append(f"Step 2 Error (Search): {e}")

    # --- STEP 3: WOS MIRROR SEARCH (Multi-Strategy) ---
    # Strategy: ISSN Match (Gold) -> Exact Name Match (Silver) -> Fuzzy Name Match (Bronze)
    results_wos = []
    try:
        candidates_by_name = []
        candidates_by_issn = []

        # 1. Search by Name (Fuzzy)
        candidates_by_name = await search_wos_mirror(query=resolved_journal_name, db=db)

        # 2. Search by ISSN (Exact) - Manual DB Filter
        if resolved_issns:
             # We query DB directly for efficiency
             issn_query = db.query(WosJournalMirror).filter(
                 or_(
                     WosJournalMirror.issn.in_(resolved_issns),
                     WosJournalMirror.eissn.in_(resolved_issns)
                 )
             ).all()

             # Convert to dict format matching search_wos_mirror output
             candidates_by_issn = [
                {
                    "id": r.wos_id,
                    "journal_name": r.journal_name,
                    "issn": r.issn,
                    "eissn": r.eissn,
                    "best_quartile": r.best_quartile,
                    "best_ranking_percent": r.best_ranking_percent,
                    "jif": r.jif,
                    "jif_5year": r.five_year_jif,
                    "categories": r.categories,
                    "ranking_category": r.ranking_category,
                    "publisher": r.publisher,
                    "source_url": r.source_url
                }
                for r in issn_query
            ]

        # 3. Prioritization Logic
        if candidates_by_issn:
            results_wos = candidates_by_issn
            status_log.append(f"Step 3: Found {len(results_wos)} WOS results via ISSN (High Confidence)")
        else:
            # Fallback to Name Check
            # Exact Name Match Filter
            exact_matches = [
                r for r in candidates_by_name
                if r['journal_name'].lower() == resolved_journal_name.lower()
            ]

            if exact_matches:
                results_wos = exact_matches
                status_log.append(f"Step 3: Found {len(results_wos)} WOS results via Exact Name Match")
            else:
                results_wos = candidates_by_name
                status_log.append(f"Step 3: Found {len(results_wos)} WOS results via Fuzzy Name Match")

    except Exception as e:
        status_log.append(f"Step 3 Error: {e}")

    # --- STEP 4: AI ANALYSIS ---
    # Only if we have something meaningful
    result_ai = None
    try:
        if resolved_journal_name and resolved_journal_name != query:
             # Meaning we resolved something
             status_log.append("Step 4: Running AI Analysis...")
             result_ai = await analyze_journal_ai(payload={
                 "journal_name": resolved_journal_name,
                 "publisher": resolved_publisher
             })
        elif not is_doi and resolved_journal_name:
             # Direct search case
             status_log.append("Step 4: Running AI Analysis (Direct)...")
             result_ai = await analyze_journal_ai(payload={
                 "journal_name": resolved_journal_name,
                 "publisher": resolved_publisher
             })

    except Exception as e:
        status_log.append(f"Step 4 Error: {e}")
        result_ai = {"error": str(e)}

    return {
        "status": "success",
        "resolved_query": {
            "original": query,
            "is_doi": is_doi,
            "journal_name": resolved_journal_name,
            "publisher": resolved_publisher
        },
        "wos_mirror": results_wos,
        # We don't necessarily return a list of OpenAlex sources here since we used it for resolution
        # But for UI consistency we can wrap the found journal in a list if found
        "openalex_sources": [{
             "journal_name": resolved_journal_name,
             "publisher": resolved_publisher,
             "source": "openalex (resolved)"
        }] if resolved_publisher != "Unknown" else [],
        "ai_analysis": result_ai,
        "debug_log": status_log
    }
