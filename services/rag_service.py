import numpy as np
import numpy as np
from typing import List, Dict, Any, Optional
import os
import sys

from database.legacy_wrapper import CecanDB

# Singleton instance for SemanticSearchEngine
_engine_instance: Optional['SemanticSearchEngine'] = None

def get_semantic_engine(api_key: str = None) -> 'SemanticSearchEngine':
    """
    Returns a singleton instance of SemanticSearchEngine.
    This ensures embeddings are loaded only once and reused across requests.
    """
    global _engine_instance
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

class SemanticSearchEngine:
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
        self.db = CecanDB()
        self.db.connect()
        self.projects = []
        self.embeddings = None
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        """Fetches all projects and generates/caches embeddings."""
        print("   [System] Initializing Semantic Search Engine (generating embeddings)...")
        self.projects = self.db.get_all_projects_for_embedding()
        
        if self.projects:
            texts = [p['text'] for p in self.projects]
            try:
                # Using the new embedding model
                result = self.genai.embed_content(
                    model="models/text-embedding-004",
                    content=texts,
                    task_type="retrieval_document",
                    title="Cecan Projects"
                )
                self.embeddings = np.array(result['embedding'])
                print(f"   [System] Generated embeddings for {len(self.projects)} projects.")
            except Exception as e:
                print(f"   [Error] Failed to generate project embeddings: {e}")
                self.embeddings = np.array([])
        else:
            print("   [System] No projects found to embed.")
            self.embeddings = np.array([])

        # Initialize Publication Embeddings (Load from DB)
        self._load_publication_embeddings()

    def _load_publication_embeddings(self):
        """Loads publication chunks and their embeddings from DB."""
        conn = self.db.conn
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, publicacion_id, content, embedding FROM publication_chunks")
            rows = cursor.fetchall()
            
            self.pub_chunks = []
            self.pub_embeddings = []
            
            for row in rows:
                if row[3]: # If embedding exists
                    import json
                    embedding = json.loads(row[3])
                    self.pub_chunks.append({
                        "id": row[0],
                        "publicacion_id": row[1],
                        "content": row[2]
                    })
                    self.pub_embeddings.append(embedding)
            
            if self.pub_embeddings:
                self.pub_embeddings = np.array(self.pub_embeddings)
                print(f"   [System] Loaded {len(self.pub_embeddings)} publication chunks.")
            else:
                self.pub_embeddings = np.array([])
                
        except Exception as e:
            print(f"   [Error] Failed to load publication embeddings: {e}")
            self.pub_embeddings = np.array([])

    def process_and_embed_publications(self):
        """Chunks and embeds publications that don't have chunks yet."""
        print("   [System] Processing publications for RAG...")
        conn = self.db.conn
        cursor = conn.cursor()
        
        # Get publications with text content
        try:
            cursor.execute("SELECT id, titulo, contenido_texto FROM publicaciones WHERE contenido_texto IS NOT NULL AND contenido_texto != ''")
            pubs = cursor.fetchall()
        except Exception as e:
            print(f"   [Error] Failed to fetch publications: {e}")
            return
        
        count = 0
        errors = 0
        
        for pub_id, title, content in pubs:
            try:
                # Check if already chunked
                cursor.execute("SELECT count(*) FROM publication_chunks WHERE publicacion_id = ?", (pub_id,))
                if cursor.fetchone()[0] > 0:
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
                
                # Batch embed
                # Note: Gemini API has limits, doing one by one or small batches is safer for now
                embeddings = []
                for idx, chunk in enumerate(chunks):
                    try:
                        emb = self.genai.embed_content(
                            model="models/text-embedding-004",
                            content=chunk,
                            task_type="retrieval_document"
                        )['embedding']
                        embeddings.append(emb)
                    except Exception as e:
                        print(f"   [Error] Failed to embed chunk {idx} of publication {pub_id}: {e}")
                        # Continue with other chunks
                        embeddings.append(None)
                
                # Save to DB (only valid embeddings)
                import json
                saved_chunks = 0
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    if emb is None:
                        continue
                    try:
                        cursor.execute("""
                            INSERT INTO publication_chunks (publicacion_id, chunk_index, content, embedding)
                            VALUES (?, ?, ?, ?)
                        """, (pub_id, i, chunk, json.dumps(emb)))
                        saved_chunks += 1
                    except Exception as e:
                        print(f"   [Error] Failed to save chunk {i} of publication {pub_id}: {e}")
                
                if saved_chunks > 0:
                    conn.commit()
                    count += 1
                    print(f"   [Success] Saved {saved_chunks} chunks for '{title}'")
                else:
                    print(f"   [Warning] No chunks saved for publication {pub_id}")
                    
            except Exception as e:
                print(f"   [Error] Failed to process publication {pub_id} ('{title}'): {e}")
                errors += 1
                continue
                
        print(f"   [System] Processed {count} publications successfully, {errors} errors.")
        # Reload embeddings
        try:
            self._load_publication_embeddings()
        except Exception as e:
            print(f"   [Error] Failed to reload embeddings: {e}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic search for the query on PROJECTS."""
        if self.embeddings is None or len(self.embeddings) == 0:
            return []

        try:
            query_embedding = self.genai.embed_content(
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
            query_embedding = self.genai.embed_content(
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
            # 1. Get Publication IDs for this academic member
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT ip.publicacion_id 
                FROM investigador_publicacion ip
                JOIN academic_members am ON ip.member_id = am.id
                WHERE am.full_name LIKE ?
            """, (f"%{researcher_name}%",))
            pub_ids = {row[0] for row in cursor.fetchall()}
            
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
            query_embedding = self.genai.embed_content(
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

    def close(self):
        self.db.close()
