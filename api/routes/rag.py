"""
RAG (Retrieval-Augmented Generation) Routes for CECAN Platform
API endpoints for semantic search and knowledge exploration
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.routes.auth import get_current_user, User

router = APIRouter(prefix="/rag", tags=["RAG & Knowledge"])


class RAGQueryRequest(BaseModel):
    """Request schema for RAG queries"""
    query: str


@router.post("/query")
async def rag_query(
    request: RAGQueryRequest
):
    """
    Perform semantic search on publication knowledge base.
    Returns relevant chunks and AI-generated synthesis.
    """
    from services.rag_service import SemanticSearchEngine
    import sqlite3
    from config import DB_PATH
    
    engine = SemanticSearchEngine()
    chunks = engine.search_knowledge(request.query, top_k=5)
    
    if not chunks:
        return {
            "results": [],
            "message": "No se encontraron resultados relevantes."
        }
    
    # Enrich with publication metadata
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    results = []
    for chunk_content in chunks:
        lines = chunk_content.split('\n', 2)
        pub_title = lines[0].replace('Publicación: ', '') if len(lines) > 0 else "Desconocido"
        content = lines[1].replace('Contenido: ', '') if len(lines) > 1 else chunk_content
        
        cursor.execute("""
            SELECT p.id, p.titulo, p.fecha, p.url_origen, p.categoria,
                   GROUP_CONCAT(i.nombre, ', ') as investigadores
            FROM Publicaciones p
            LEFT JOIN Investigador_Publicacion ip ON p.id = ip.publicacion_id
            LEFT JOIN Investigadores i ON ip.investigador_id = i.id
            WHERE p.titulo LIKE ?
            GROUP BY p.id
            LIMIT 1
        """, (f'%{pub_title[:30]}%',))
        
        pub_data = cursor.fetchone()
        
        if pub_data:
            results.append({
                "id": pub_data['id'],
                "titulo": pub_data['titulo'],
                "fecha": pub_data['fecha'],
                "url": pub_data['url_origen'],
                "categoria": pub_data['categoria'],
                "investigadores": pub_data['investigadores'],
                "chunk_relevante": content[:500]
            })
    
    conn.close()
    
    # Generate synthesis with AI
    from services.agent_service import CecanAgent
    
    agent = CecanAgent()
    context = "\n\n".join([f"- {r['titulo']}: {r['chunk_relevante']}" for r in results[:3]])
    prompt = f"""Basándote en estos fragmentos relevantes de publicaciones científicas, 
responde la pregunta: "{request.query}"

Contexto:
{context}

Proporciona una respuesta sintética y precisa."""
    
    synthesis = agent.send_message(prompt)
    agent.close()
    
    return {
        "query": request.query,
        "synthesis": synthesis,
        "results": results
    }


@router.get("/stats")
async def get_rag_stats(current_user: User = Depends(get_current_user)):
    """Get RAG system statistics"""
    import sqlite3
    from config import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM PublicationChunks")
    total_chunks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT publicacion_id) FROM PublicationChunks")
    indexed_pubs = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_chunks": total_chunks,
        "indexed_publications": indexed_pubs,
        "embedding_model": "text-embedding-004",
        "chunk_size": 1000
    }


@router.get("/publications-stats")
async def get_publications_stats(current_user: User = Depends(get_current_user)):
    """Returns statistics about publications and RAG processing"""
    import sqlite3
    from config import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total publications
    cursor.execute("SELECT COUNT(*) as total FROM Publicaciones")
    total_pubs = cursor.fetchone()['total']
    
    # Publications with content
    cursor.execute("SELECT COUNT(*) as total FROM Publicaciones WHERE contenido_texto IS NOT NULL AND contenido_texto != ''")
    pubs_with_content = cursor.fetchone()['total']
    
    # Total chunks
    cursor.execute("SELECT COUNT(*) as total FROM PublicationChunks")
    total_chunks = cursor.fetchone()['total']
    
    conn.close()
    
    return {
        "total_publicaciones": total_pubs,
        "publicaciones_procesadas": pubs_with_content,
        "total_chunks": total_chunks,
        "porcentaje_procesado": round((pubs_with_content / total_pubs * 100) if total_pubs > 0 else 0, 1)
    }


@router.get("/suggested-queries")
async def get_suggested_queries():
    """Returns suggested queries for the RAG system"""
    return {
        "queries": [
            "¿Qué investigaciones hay sobre prevención del cáncer?",
            "¿Cómo se relaciona el cáncer gástrico con la dieta?",
            "¿Qué dice la investigación sobre políticas públicas en oncología?",
            "¿Cuáles son los factores de riesgo del cáncer de mama?",
            "¿Qué avances hay en tratamientos oncológicos?",
            "¿Cómo afecta el acceso a la salud en el diagnóstico temprano?",
            "¿Qué rol juega la genética en el cáncer?",
            "¿Cuáles son las estrategias de prevención más efectivas?"
        ]
    }


class ChatRequest(BaseModel):
    """Request schema for chat messages"""
    message: str


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest
):
    """Chat with the CECAN AI agent"""
    from services.agent_service import CecanAgent
    
    try:
        agent = CecanAgent()
        response = agent.send_message(request.message)
        agent.close()
        return {"response": response}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")
