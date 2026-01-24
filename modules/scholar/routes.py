"""
FastAPI Routes para Semantic Scholar Integration
Módulo autocontenido - comentar 1 línea en main.py para desactivar
"""
from fastapi import APIRouter, HTTPException, Depends
from .client import SemanticScholarClient
from .models import SmartPaperResponse
import os

router = APIRouter(prefix="/api/scholar", tags=["Scholar Intelligence"])

# ============================================================================
# DEPENDENCY: Cliente Singleton
# ============================================================================
_client_instance = None

def get_scholar_client() -> SemanticScholarClient:
    """
    Retorna una instancia singleton del cliente.
    Esto asegura que el Rate Limiter sea compartido entre todas las requests.
    """
    global _client_instance
    if _client_instance is None:
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        _client_instance = SemanticScholarClient(api_key=api_key)
    return _client_instance

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/papers/enrich/{paper_id:path}", response_model=SmartPaperResponse)
async def enrich_paper(
    paper_id: str,
    client: SemanticScholarClient = Depends(get_scholar_client)
):
    """
    Obtiene inteligencia completa de un paper (TLDR, embeddings, citations).
    
    Args:
        paper_id: DOI, Semantic Scholar Paper ID, o ArXiv ID
    
    Returns:
        SmartPaperResponse con todos los campos enriquecidos
    """
    result = await client.get_paper_intelligence(paper_id)
    
    if result.get("paperId") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="Paper not found in Semantic Scholar")
    
    return result

@router.get("/papers/{paper_id:path}/genealogy")
async def get_paper_genealogy(
    paper_id: str,
    client: SemanticScholarClient = Depends(get_scholar_client)
):
    """
    Obtiene el grafo de referencias de un paper.
    
    Returns:
        {"nodes": [...], "links": [...]} listo para react-force-graph
    """
    return await client.get_paper_genealogy(paper_id)

@router.get("/autocomplete")
async def autocomplete_search(
    query: str,
    client: SemanticScholarClient = Depends(get_scholar_client)
):
    """
    Busca autores y papers para autocompletado.
    
    Args:
        query: Término de búsqueda
    
    Returns:
        {"matches": [{"id": "...", "title": "...", "type": "paper|author"}]}
    """
    if not query or len(query) < 2:
        return {"matches": []}
    
    return await client.get_autocomplete(query)

@router.post("/search")
async def search_papers(
    body: dict,
    client: SemanticScholarClient = Depends(get_scholar_client)
):
    """
    Búsqueda completa de papers.
    
    Body:
        {"query": "deep learning transformers"}
    
    Returns:
        {"total": 1234, "data": [...]}
    """
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    # Nota: Este método no existe en el client.py actual
    # Si lo necesitas, agrégalo o usa autocomplete
    return {"total": 0, "data": [], "message": "Implement search_papers in client.py"}

# ============================================================================
# HEALTH CHECK  
# ============================================================================
@router.get("/health")
async def health_check():
    """Verifica que el módulo esté cargado correctamente"""
    return {
        "status": "healthy",
        "module": "semantic_scholar_integration",
        "api_key_configured": bool(os.getenv("SEMANTIC_SCHOLAR_API_KEY"))
    }
