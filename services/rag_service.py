import numpy as np
from typing import List, Dict, Any, Optional
import os
import sys
import threading
import json
from pathlib import Path

# Database
from database.session import get_session
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.models import (
    Project, WorkPackage, AcademicMember, ProjectResearcher, 
    Publication, PublicationChunk, ResearcherPublication
)

# Tenacity for API retry logic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging

# Configure logging for retry
logger = logging.getLogger(__name__)

# FAISS persistence path
from config import VECTORSTORE_DIR
VECTORSTORE_PATH = VECTORSTORE_DIR / "projects"

# Singleton instance for SemanticSearchEngine
_engine_instance: Optional['SemanticSearchEngine'] = None
_lock = threading.Lock()

def get_semantic_engine(api_key: str = None) -> 'SemanticSearchEngine':
    """
    Returns a singleton instance of SemanticSearchEngine.
    This ensures embeddings are loaded only once and reused across requests.
    Thread-safe implementation.
    """
    global _engine_instance
    with _lock:
        if _engine_instance is None:
            print("   [System] Creating new SemanticSearchEngine singleton...")
            _engine_instance = SemanticSearchEngine(api_key=api_key)
    return _engine_instance

def reset_semantic_engine():
    """Resets the singleton instance. Use only for testing or forced refresh."""
    global _engine_instance
    if _engine_instance:
        _engine_instance.close()
        _engine_instance = None

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
    retry=retry_if_exception_type(Exception),
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(5),
    before_sleep=lambda retry_state: print(
        f"   ⚠️ Gemini API rate limit hit. Waiting {retry_state.next_action.sleep} seconds before retry {retry_state.attempt_number}/5..."
    ),
    reraise=True
)
def call_gemini_with_retry(genai_module, model: str, content, task_type: str, title: str = None):
    """
    Wrapper for genai.embed_content with automatic retry logic.
    Handles rate limits (429) with exponential backoff.
    """
    try:
        kwargs = {
            'model': model,
            'content': content,
            'task_type': task_type
        }
        if title:
            kwargs['title'] = title
        
        return genai_module.embed_content(**kwargs)
    except Exception as e:
        # Only retry if it's a rate limit error
        if _is_rate_limit_error(e):
            print(f"   ⚠️ Rate limit error detected: {str(e)[:100]}")
            raise  # Will trigger retry
        else:
            # Non-rate-limit errors should fail immediately
            print(f"   ❌ Non-retryable Gemini API error: {str(e)[:100]}")
            raise

class SemanticSearchEngine:
    """Semantic search engine using Gemini embeddings and FAISS."""

    def __init__(self, api_key=None):
        import google.generativeai as genai
        self.genai = genai
        
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
            # Log warning instead of crashing, to allow app to start
            print("Warning: GOOGLE_API_KEY not found. Semantic search will be disabled.")
            self.embeddings = np.array([])
            self.pub_embeddings = np.array([])
            return

        self.genai.configure(api_key=api_key)
        # No persistent DB connection - assume sessions are created per method
        self.projects = []
        self.embeddings = None
        self._initialize_embeddings()

    def _get_projects_for_embedding(self):
        """Fetches all projects with rich context for embedding."""
        session = get_session()
        try:
            # Fetch all projects with relationships
            projects = session.query(Project).all()
            
            project_data = []
            for p in projects:
                # Build context string
                wp_name = p.wp.nombre if p.wp else "Sin WP"
                
                # Researchers
                researchers_txt = []
                for pr in p.researcher_connections:
                    name = pr.member.full_name
                    role = pr.rol or "Miembro"
                    researchers_txt.append(f"{name} ({role})")
                
                # Nodes
                nodes_txt = [pn.node.nombre for pn in p.node_connections]
                
                full_text = f"Título: {p.titulo}. WP: {wp_name}. Nodos: {', '.join(nodes_txt)}. Investigadores: {', '.join(researchers_txt)}"
                
                project_data.append({
                    "metadata": {
                        "id": p.id,
                        "titulo": p.titulo,
                        "wp_nombre": wp_name
                    },
                    "text": full_text
                })
            return project_data
        finally:
            session.close()

    def _initialize_embeddings(self):
        """Fetches all projects and generates/caches embeddings."""
        
        # Check if persisted index exists
        if VECTORSTORE_PATH.exists() and (VECTORSTORE_PATH / "index.faiss").exists():
            print("   [System] Loading existing project embeddings from disk...")
            self._load_embeddings_from_disk()
        else:
            print("   [System] No cached embeddings found. Generating and saving new embeddings...")
            self._generate_and_save_embeddings()
        
        # Initialize Publication Embeddings (Load from DB)
        self._load_publication_embeddings()
    
    def _load_embeddings_from_disk(self):
        """Loads project embeddings from FAISS index on disk."""
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_community.embeddings import FakeEmbeddings
            
            # Load FAISS index
            vectorstore = FAISS.load_local(
                str(VECTORSTORE_PATH),
                FakeEmbeddings(size=768),  # text-embedding-004 produces 768-dim vectors
                allow_dangerous_deserialization=True
            )
            
            # Reconstruct projects and embeddings
            self.projects = self._get_projects_for_embedding()
            self.embeddings = np.array([vectorstore.index.reconstruct(i) for i in range(vectorstore.index.ntotal)])
            
            print(f"   [System] Loaded {len(self.projects)} project embeddings from disk.")
        except Exception as e:
            print(f"   [Error] Failed to load embeddings from disk: {e}")
            print("   [System] Falling back to regeneration...")
            self._generate_and_save_embeddings()
    
    def _generate_and_save_embeddings(self):
        """Generates embeddings for all projects and saves them to disk."""
        self.projects = self._get_projects_for_embedding()
        
        if not self.projects:
            print("   [System] No projects found to embed.")
            self.embeddings = np.array([])
            return
        
        texts = [p['text'] for p in self.projects]
        
        try:
            # Generate embeddings using Gemini (with retry logic)
            result = call_gemini_with_retry(
                self.genai,
                model="models/text-embedding-004",
                content=texts,
                task_type="retrieval_document",
                title="Cecan Projects"
            )
            self.embeddings = np.array(result['embedding'])
            print(f"   [System] Generated embeddings for {len(self.projects)} projects.")
            
            # Save to FAISS index
            self._save_embeddings_to_disk()
            
        except Exception as e:
            print(f"   [Error] Failed to generate project embeddings: {e}")
            self.embeddings = np.array([])
    
    def _save_embeddings_to_disk(self):
        """Saves project embeddings to FAISS index on disk."""
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_community.docstore.in_memory import InMemoryDocstore
            from langchain_community.embeddings import FakeEmbeddings
            import faiss
            
            # Create FAISS index
            dimension = self.embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(self.embeddings.astype('float32'))
            
            # Create vector store
            fake_embeddings = FakeEmbeddings(size=dimension)
            docstore = InMemoryDocstore({})
            index_to_docstore_id = {}
            
            vectorstore = FAISS(
                embedding_function=fake_embeddings,
                index=index,
                docstore=docstore,
                index_to_docstore_id=index_to_docstore_id
            )
            
            # Save to disk
            VECTORSTORE_PATH.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(VECTORSTORE_PATH))
            
            print(f"   [System] Saved {len(self.embeddings)} embeddings to {VECTORSTORE_PATH}")
            
        except Exception as e:
            print(f"   [Error] Failed to save embeddings to disk: {e}")

    def _load_publication_embeddings(self):
        """Loads publication chunks and their embeddings from DB."""
        session = get_session()
        try:
            chunks = session.query(PublicationChunk).all()
            
            self.pub_chunks = []
            self.pub_embeddings = []
            
            for chunk in chunks:
                if chunk.embedding: # If embedding exists
                    import json
                    try:
                        embedding = json.loads(chunk.embedding)
                        self.pub_chunks.append({
                            "id": chunk.id,
                            "publicacion_id": chunk.publicacion_id,
                            "content": chunk.content
                        })
                        self.pub_embeddings.append(embedding)
                    except json.JSONDecodeError:
                        continue
            
            if self.pub_embeddings:
                self.pub_embeddings = np.array(self.pub_embeddings)
                print(f"   [System] Loaded {len(self.pub_embeddings)} publication chunks.")
            else:
                self.pub_embeddings = np.array([])
                
        except Exception as e:
            print(f"   [Error] Failed to load publication embeddings: {e}")
            self.pub_embeddings = np.array([])
        finally:
            session.close()

    def process_single_publication(self, pub_id: int) -> dict:
        """
        Procesa y embebea una sola publicación recién subida.
        Retorna metadata de procesamiento para feedback al usuario.
        """
        session = get_session()
        
        try:
            # 1. Fetch publication (join not needed but good for future)
            # Use filter instead of execute
            pub = session.query(Publication).filter(Publication.id == pub_id).first()
            
            if not pub:
                return {"success": False, "error": "Publication not found"}
            
            title = pub.titulo
            content = pub.contenido_texto
            
            # 2. Validate content
            if not content or len(content) < 100:
                return {"success": False, "error": "Insufficient content (menos de 100 caracteres)", "chunks_created": 0}
            
            # 3. Check if already processed
            existing_chunks = session.query(func.count(PublicationChunk.id)).filter(PublicationChunk.publicacion_id == pub_id).scalar()
            if existing_chunks > 0:
                print(f"   [RAG] Publication {pub_id} already indexed with {existing_chunks} chunks")
                return {"success": True, "already_indexed": True, "chunks_created": existing_chunks}
            
            # 4. Generate chunks
            chunk_size = 1000
            overlap = 200
            chunks = []
            
            for i in range(0, len(content), chunk_size - overlap):
                chunk_text = content[i:i + chunk_size]
                if len(chunk_text) < 100:
                    continue
                full_chunk = f"Publicación: {title}\nContenido: {chunk_text}"
                chunks.append(full_chunk)
            
            if not chunks:
                return {"success": False, "error": "No valid chunks created", "chunks_created": 0}
            
            # 5. Generate embeddings
            import json
            saved_chunks = 0
            failed_chunks = 0
            
            for idx, chunk in enumerate(chunks):
                try:
                    emb = call_gemini_with_retry(
                        self.genai,
                        model="models/text-embedding-004",
                        content=chunk,
                        task_type="retrieval_document"
                    )['embedding']
                    
                    new_chunk = PublicationChunk(
                        publicacion_id=pub_id,
                        chunk_index=idx,
                        content=chunk,
                        embedding=json.dumps(emb)
                    )
                    session.add(new_chunk)
                    saved_chunks += 1
                except Exception as e:
                    print(f"   [Error] Failed to embed chunk {idx} of publication {pub_id}: {e}")
                    failed_chunks += 1
                    continue
            
            if saved_chunks > 0:
                session.commit()
                
                # 6. Reload embeddings in memory
                print(f"   [RAG] Reloading embeddings to include new publication...")
                # Important: Close session before calling another method that might use DB
                # But here _load_publication_embeddings uses its own session, so it is safe inside or outside, 
                # but better to finish transaction first.
                
                # Small optimization: Update in-memory lists directly instead of full reload?
                # For now, full reload is safer for consistency.
                self._load_publication_embeddings()
                
                print(f"   [Success] Publication '{title}' indexed: {saved_chunks} chunks saved, {failed_chunks} failed")
                
                return {
                    "success": True,
                    "chunks_created": saved_chunks,
                    "chunks_failed": failed_chunks,
                    "publication_title": title,
                    "now_searchable": True,
                    "already_indexed": False
                }
            else:
                return {"success": False, "error": "Failed to save any chunks", "chunks_created": 0}
                
        except Exception as e:
            session.rollback()
            print(f"   [Error] Failed to process single publication {pub_id}: {e}")
            return {"success": False, "error": str(e), "chunks_created": 0}
        finally:
            session.close()

    def process_and_embed_publications(self):
        """Chunks and embeds publications that don't have chunks yet."""
        print("   [System] Processing publications for RAG...")
        session = get_session()
        
        try:
            # Get publications with text content that are not fully chunked
            # Simplified: just get all with content and check one by one (as before)
            # or usage exclusion join. For now, stick to original logic: check count for each.
            pubs = session.query(Publication).filter(Publication.contenido_texto.isnot(None), Publication.contenido_texto != '').all()
            
            count = 0
            errors = 0
            
            for pub in pubs:
                pub_id = pub.id
                title = pub.titulo
                content = pub.contenido_texto
                
                try:
                    # Check if already chunked
                    existing_chunks = session.query(func.count(PublicationChunk.id)).filter(PublicationChunk.publicacion_id == pub_id).scalar()
                    if existing_chunks > 0:
                        continue
                        
                    print(f"   [RAG] Processing '{title}'...")
                    
                    # Validate content
                    if not content or len(content) < 100:
                        print(f"   [Warning] Publication {pub_id} has insufficient content, skipping.")
                        continue
                    
                    # Simple chunking: 1000 chars with overlap
                    chunk_size = 1000
                    overlap = 200
                    chunks = []
                    
                    for i in range(0, len(content), chunk_size - overlap):
                        chunk_text = content[i:i + chunk_size]
                        if len(chunk_text) < 100: continue # Skip too small chunks
                        
                        # Add context to chunk
                        full_chunk = f"Publicación: {title}\nContenido: {chunk_text}"
                        chunks.append(full_chunk)
                    
                    if not chunks:
                        print(f"   [Warning] No valid chunks created for publication {pub_id}")
                        continue
                    
                    # Batch embed (one by one for safety)
                    embeddings = []
                    for idx, chunk in enumerate(chunks):
                        try:
                            emb = call_gemini_with_retry(
                                self.genai,
                                model="models/text-embedding-004",
                                content=chunk,
                                task_type="retrieval_document"
                            )['embedding']
                            embeddings.append(emb)
                        except Exception as e:
                            print(f"   [Error] Failed to embed chunk {idx} of publication {pub_id}: {e}")
                            embeddings.append(None)
                    
                    # Save to DB (only valid embeddings)
                    import json
                    saved_chunks = 0
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                        if emb is None:
                            continue
                        try:
                            new_chunk = PublicationChunk(
                                publicacion_id=pub_id,
                                chunk_index=i,
                                content=chunk,
                                embedding=json.dumps(emb)
                            )
                            session.add(new_chunk)
                            saved_chunks += 1
                        except Exception as e:
                            print(f"   [Error] Failed to save chunk {i} of publication {pub_id}: {e}")
                    
                    if saved_chunks > 0:
                        session.commit()
                        count += 1
                        print(f"   [Success] Saved {saved_chunks} chunks for '{title}'")
                    else:
                        print(f"   [Warning] No chunks saved for publication {pub_id}")
                        
                except Exception as e:
                    session.rollback()
                    print(f"   [Error] Failed to process publication {pub_id} ('{title}'): {e}")
                    errors += 1
                    continue
                    
            print(f"   [System] Processed {count} publications successfully, {errors} errors.")
            
            # Reload embeddings
            # (outside the loop to be efficient)
            try:
                self._load_publication_embeddings()
            except Exception as e:
                print(f"   [Error] Failed to reload embeddings: {e}")
                
        except Exception as e:
             print(f"   [Error] General failure in process_and_embed_publications: {e}")
        finally:
            session.close()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic search for the query on PROJECTS."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        try:
            query_embedding = call_gemini_with_retry(
                self.genai,
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )['embedding']
            
            query_vec = np.array(query_embedding)
            scores = np.dot(self.embeddings, query_vec)
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                project = self.projects[idx]
                results.append({
                    "project": project['metadata'],
                    "score": float(scores[idx]),
                    "match_reason": "Semantic Match"
                })
                
            return results
        except Exception as e:
            print(f"   [Error] Semantic search failed: {e}")
            return []

    def search_knowledge(self, query: str, top_k: int = 3) -> List[str]:
        """Performs semantic search on PUBLICATION CHUNKS (RAG)."""
        if self.pub_embeddings is None or len(self.pub_embeddings) == 0:
            return []

        try:
            query_embedding = call_gemini_with_retry(
                self.genai,
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )['embedding']
            
            query_vec = np.array(query_embedding)
            scores = np.dot(self.pub_embeddings, query_vec)
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                chunk = self.pub_chunks[idx]
                results.append(chunk['content'])
                
            return results
        except Exception as e:
            print(f"   [Error] Knowledge search failed: {e}")
            return []

    def search_researcher_knowledge(self, query: str, researcher_name: str, top_k: int = 5) -> List[str]:
        """Performs semantic search on PUBLICATION CHUNKS, filtered by academic member."""
        if self.pub_embeddings is None or len(self.pub_embeddings) == 0:
            return []

        try:
            # 1. Get Publication IDs for this academic member (SQLAlchemy ORM)
            session = get_session()
            try:
                results = (
                    session.query(ResearcherPublication.publicacion_id)
                    .join(AcademicMember, ResearcherPublication.member_id == AcademicMember.id)
                    .filter(AcademicMember.full_name.ilike(f"%{researcher_name}%"))
                    .all()
                )
                pub_ids = {row[0] for row in results}
            finally:
                session.close()
            
            if not pub_ids:
                return [f"No se encontraron publicaciones para el investigador '{researcher_name}'."]

            # 2. Filter chunks and embeddings
            filtered_indices = []
            for i, chunk in enumerate(self.pub_chunks):
                if chunk['publicacion_id'] in pub_ids:
                    filtered_indices.append(i)
            
            if not filtered_indices:
                return [f"El investigador '{researcher_name}' tiene publicaciones asociadas, pero no tienen contenido procesado (PDFs no leídos)."]

            filtered_embeddings = self.pub_embeddings[filtered_indices]
            
            # 3. Perform Search
            query_embedding = call_gemini_with_retry(
                self.genai,
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )['embedding']
            
            query_vec = np.array(query_embedding)
            scores = np.dot(filtered_embeddings, query_vec)
            
            # Get top K from the filtered set
            # scores is same length as filtered_indices
            top_local_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for local_idx in top_local_indices:
                original_idx = filtered_indices[local_idx]
                chunk = self.pub_chunks[original_idx]
                results.append(chunk['content'])
                
            return results

        except Exception as e:
            print(f"   [Error] Researcher knowledge search failed: {e}")
            return []

    def refresh_index(self):
        """Forces regeneration of project embeddings index."""
        print("   [System] Forcing refresh of project embeddings...")
        
        # Delete existing cache
        if VECTORSTORE_PATH.exists():
            import shutil
            shutil.rmtree(VECTORSTORE_PATH)
            print("   [System] Deleted existing cache.")
        
        # Regenerate
        self._generate_and_save_embeddings()
        print("   [System] Index refresh complete.")
    
    def close(self):
        # Database sessions are ephemeral, so no need to close a global connection.
        pass
