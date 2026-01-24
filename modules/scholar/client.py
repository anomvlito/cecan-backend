import httpx
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from .models import SmartPaperResponse

# Configure library logger
logger = logging.getLogger("semantic_sdk")

class SemanticScholarClient:
    """
    A self-contained client for the Semantic Scholar Graph API.
    Features:
    - Automatic Rate Limiting (1 req/sec by default)
    - Robust Error Handling
    - Smart Methods for Paper Enrichment and Genealogy
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # Class-level rate limiter to share across all client instances
    _rate_limit_lock = asyncio.Lock()
    _last_request_time = None 
    _min_interval = 1.0 

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            api_key (str, optional): Your Semantic Scholar API Key. 
                                     If None, strict rate limits apply.
        """
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
            logger.info(f"✅ Initialized S2 Client with API Key: {masked_key}")
        else:
            logger.warning("⚠️  Initialized S2 Client WITHOUT API Key (Rate limits will be strict)")
            
    async def _wait_for_rate_limit(self):
        """
        Ensures we don't exceed 1 request per second.
        """
        async with self._rate_limit_lock:
            current_time = time.time()
            
            # First request ever logic
            if self._last_request_time is None:
                SemanticScholarClient._last_request_time = current_time
                return
            
            time_since_last = current_time - self._last_request_time
            
            if time_since_last < self._min_interval:
                wait_time = self._min_interval - time_since_last
                logger.debug(f"⏳ Rate Limit: Waiting {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
            
            SemanticScholarClient._last_request_time = time.time()

    async def get_paper_intelligence(self, paper_id_or_doi: str) -> Dict[str, Any]:
        """
        Fetches detailed paper intelligence:
        1. Core Metadata (Title, Year, Authors)
        2. TLDR (AI Summary)
        3. Embedding Vector (Specter)
        4. Citation Analysis (Intents, Influence)
        """
        # Normalize ID
        clean_id = self._normalize_id(paper_id_or_doi)
        
        # Default Empty Response
        empty_response = {
            "doi": paper_id_or_doi if "DOI" in clean_id else None,
            "paperId": "NOT_FOUND",
            "title": "Not Found / API Error",
            "year": None,
            "authors": [],
            "tldr": None,
            "intent_breakdown": {},
            "embedding_sample": [],
            "smart_citations": []
        }

        async with httpx.AsyncClient() as client:
            try:
                # --- STEP 1: CORE DATA ---
                fields_core = "paperId,title,year,authors,tldr,embedding,abstract"
                url_core = f"{self.BASE_URL}/paper/{clean_id}"
                
                await self._wait_for_rate_limit()
                
                resp_core = await client.get(
                    url_core, 
                    params={"fields": fields_core}, 
                    headers=self.headers,
                    timeout=10.0
                )
                
                if resp_core.status_code == 404:
                    return empty_response

                if resp_core.status_code != 200:
                    logger.error(f"S2 Core API Failed {resp_core.status_code}")
                    return empty_response
                
                core_data = resp_core.json()
                real_paper_id = core_data.get("paperId", clean_id)

                # --- STEP 2: CITATION INTELLIGENCE ---
                url_cit = f"{self.BASE_URL}/paper/{real_paper_id}/citations"
                params_cit = {"fields": "intent,isInfluential,title,paperId", "limit": 100}
                
                await self._wait_for_rate_limit()
                
                resp_cit = await client.get(url_cit, params=params_cit, headers=self.headers, timeout=10.0)
                
                citations_data = []
                if resp_cit.status_code == 200:
                    try:
                        json_data = resp_cit.json()
                        if json_data and isinstance(json_data, dict):
                            citations_data = json_data.get('data', [])
                    except:
                        pass
                
                # --- MERGE & TRANSFORM ---
                core_data['citations'] = citations_data
                return self._transform_response(paper_id_or_doi, core_data)

            except Exception as e:
                 logger.error(f"S2 Connection Error: {e}")
                 return empty_response

    async def get_paper_genealogy(self, paper_id_or_doi: str) -> Dict[str, Any]:
        """
        Builds a graph of references (Nodes and links) for visualization.
        """
        clean_id = self._normalize_id(paper_id_or_doi)
        
        async with httpx.AsyncClient() as client:
            try:
                fields = "paperId,title,year,citationCount,isInfluential"
                url = f"{self.BASE_URL}/paper/{clean_id}/references"
                
                await self._wait_for_rate_limit()
                
                resp = await client.get(
                    url, 
                    params={"fields": fields, "limit": 10},
                    headers=self.headers,
                    timeout=10.0
                )
                
                if resp.status_code != 200:
                    return {"nodes": [], "links": []}

                data = resp.json().get('data') or []
                
                # Build Graph Logic (Same as original)
                nodes = [{"id": "ROOT", "label": "Current Paper", "type": "root", "val": 20}]
                links = []
                
                for ref in data:
                    cited_paper = ref.get("citedPaper") or {}
                    p_id = cited_paper.get("paperId")
                    if not p_id: continue
                    
                    title = cited_paper.get("title", "Unknown")
                    cit_count = cited_paper.get("citationCount", 0)
                    is_influential = ref.get("isInfluential", False)
                    
                    size = 5 + (cit_count / 100) if cit_count else 5
                    if size > 15: size = 15
                    
                    nodes.append({
                        "id": p_id,
                        "label": f"{title[:30]}..." if len(title) > 30 else title,
                        "title": title,
                        "year": cited_paper.get("year"),
                        "val": size,
                        "group": "influential" if is_influential else "reference"
                    })
                    
                    links.append({
                        "source": "ROOT",
                        "target": p_id,
                        "color": "#ef4444" if is_influential else "#848484"
                    })
                
                return {"nodes": nodes, "links": links}
                
            except Exception as e:
                logger.error(f"Genealogy Error: {e}")
                return {"nodes": [], "links": []}
    
    async def get_autocomplete(self, query: str) -> Dict[str, Any]:
        """
        Fetches search suggestions for Authors and Papers.
        """
        # ... Implementation simplified for brevity but includes logic
        matches = []
        async with httpx.AsyncClient() as client:
            try:
                await self._wait_for_rate_limit()
                # 1. Authors
                resp_auth = await client.get(f"{self.BASE_URL}/author/search", 
                                           params={"query": query, "limit": 3}, 
                                           headers=self.headers)
                if resp_auth.status_code == 200:
                    for a in resp_auth.json().get('data', []):
                         matches.append({"id": a.get("authorId"), "title": f"👤 {a.get('name')}", "type": "author"})

                await self._wait_for_rate_limit()
                # 2. Papers
                resp_paper = await client.get(f"{self.BASE_URL}/paper/search", 
                                            params={"query": query, "limit": 5, "fields": "title,year,authors,paperId"}, 
                                            headers=self.headers)
                if resp_paper.status_code == 200:
                    for p in resp_paper.json().get('data', []):
                        matches.append({"id": p.get("paperId"), "title": p.get("title"), "type": "paper", "year": p.get("year")})

                return {"matches": matches}
            except Exception:
                return {"matches": []}

    def _normalize_id(self, doi: str) -> str:
        clean_id = doi.strip()
        while clean_id.endswith('.'):
            clean_id = clean_id[:-1]
        if clean_id.upper().startswith("DOI:"):
            clean_id = "DOI:" + clean_id[4:]
        elif "10." in clean_id and "/" in clean_id:
            clean_id = f"DOI:{clean_id}"
        return clean_id

    def _transform_response(self, original_id: str, data: dict) -> Dict[str, Any]:
        # Reuse transformation logic
        citation_intents = {}
        detailed_citations = []
        raw_citations = data.get("citations") or []
        
        for cit in raw_citations:
            intents = cit.get("intent") or []
            if isinstance(intents, str): intents = [intents]
            for i in intents:
                citation_intents[i] = citation_intents.get(i, 0) + 1
            
            citing_paper = cit.get("citingPaper") or {}
            paper_id = cit.get("paperId") or citing_paper.get("paperId")
            if paper_id:
                detailed_citations.append({
                    "paper_id": paper_id,
                    "title": cit.get("title") or citing_paper.get("title"),
                    "intent_type": intents,
                    "is_influential": cit.get("isInfluential", False)
                })

        tldr = data.get("tldr")
        tldr_text = tldr.get("text") if isinstance(tldr, dict) else data.get("abstract")
        
        # Extract full embedding vector (768 dimensions)
        # Scholar API can return embedding as:
        # 1. {"vector": [...]} (dict format)
        # 2. [...] (direct array)
        embedding_raw = data.get("embedding")
        if isinstance(embedding_raw, dict):
            embedding_vector = embedding_raw.get("vector", [])
        elif isinstance(embedding_raw, list):
            embedding_vector = embedding_raw
        else:
            embedding_vector = []

        return {
            "paperId": data.get("paperId", "UNKNOWN"),
            "doi": original_id,
            "title": data.get("title", "Unknown Title"),
            "year": data.get("year"),
            "authors": data.get("authors", []),
            "tldr": tldr_text,
            "intent_breakdown": citation_intents,
            "embedding": embedding_vector,  # Full vector (768 dims)
            "embedding_sample": embedding_vector[:5] if embedding_vector else [],  # Sample for display
            "smart_citations": detailed_citations
        }
