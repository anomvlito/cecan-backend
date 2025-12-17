import os
from dotenv import load_dotenv

load_dotenv()
from collections.abc import Iterable
import sys

from database.legacy_wrapper import CecanDB
from services.rag_service import get_semantic_engine


class CecanAgent:
    def __init__(self, api_key=None):
        import google.generativeai as genai
        self.genai = genai
        
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found. Please set it in your environment variables or pass it to the constructor.")

        self.genai.configure(api_key=api_key)
        
        self.db = CecanDB()
        self.db.connect()
        
        # Initialize Semantic Search Engine (uses singleton)
        try:
            self.semantic_engine = get_semantic_engine(api_key=api_key)
        except Exception as e:
            print(f"Warning: Semantic search could not be initialized: {e}")
            self.semantic_engine = None
        
        self.tools = [
            self.search_projects,
            self.conceptual_search,
            self.get_project_details,
            self.list_all_wps,
            self.consult_researcher_knowledge
        ]
        
        # Get model name from environment variable
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
        
        self.model = self.genai.GenerativeModel(
            model_name=model_name,
            tools=self.tools,
            system_instruction=self._get_system_instruction()
        )
        
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def _get_system_instruction(self):
        return """
        Eres el Estratega de Investigación del CECAN. Tu misión es comunicar el valor y la estrategia del centro de manera clara, experta y fluida.
        
        TU OBJETIVO PRINCIPAL:
        Responder directamente a la inquietud del usuario con un análisis rico y bien fundamentado.
        
        REGLA DE ORO - "SHOW, DON'T TELL":
        - **NUNCA** expliques qué herramientas vas a usar ni qué pasos vas a seguir ("Primero buscaré...", "Usaré la función...").
        - **NUNCA** digas "Para responder a esto necesito...". Simplemente HAZLO y da la respuesta.
        - Si necesitas buscar información, hazlo silenciosamente y presenta solo el hallazgo final.
        
        TU ESTILO DE RESPUESTA:
        1.  **Narrativo y Fluido:** Escribe como un experto humano conversando. Usa párrafos cohesivos. Evita el exceso de listas o viñetas.
        2.  **Sintético pero Profundo:** Ve al grano. No rellenes con obviedades.
        3.  **Conectado:** Relaciona siempre el tema con la estrategia mayor del CECAN (interdisciplina, impacto público, prevención).
        
        USO DE INFORMACIÓN:
        - Si te preguntan por un **AcademicMember**: Consulta sus publicaciones (tool: `consult_researcher_knowledge`) y sintetiza sus líneas de investigación, metodologías y aportes clave. No listes papers, explica sus ideas.
        - Si te preguntan por un **Proyecto**: Explica su relevancia, quiénes lo lideran y cómo se conecta con otros temas (WPs/Nodos).
        - Si te preguntan por un **Nodo/Tema**: Explica qué es, por qué es crítico y menciona ejemplos de proyectos o AcademicMemberes que lo abordan.
        
        Si la información es insuficiente, haz una deducción inteligente basada en el contexto o sugiere una perspectiva relacionada, pero no te quedes en blanco ni pidas disculpas excesivas.
        
        Sé el experto que conecta los puntos.
        """

    def search_projects(self, keyword: str):
        """Busca proyectos por título, AcademicMember, nodo o WP (coincidencia exacta o parcial de texto)."""
        print(f"   [Tool] Buscando proyectos (SQL) con: '{keyword}'...")
        return self.db.search_projects(keyword)

    def conceptual_search(self, query: str):
        """Busca proyectos conceptualmente relacionados usando inteligencia artificial (búsqueda semántica)."""
        print(f"   [Tool] Buscando proyectos (Semántico) con: '{query}'...")
        if self.semantic_engine:
            return self.semantic_engine.search(query)
        else:
            return "La búsqueda semántica no está disponible en este momento."

    def consult_researcher_knowledge(self, query: str, researcher_name: str):
        """Busca información específica en las publicaciones (PDFs) de un AcademicMember. Úsalo para responder preguntas sobre 'qué dice X sobre Y'."""
        print(f"   [Tool] Consultando conocimiento del AcademicMember '{researcher_name}' sobre: '{query}'...")
        if self.semantic_engine:
            results = self.semantic_engine.search_researcher_knowledge(query, researcher_name)
            return results
        else:
            return "La búsqueda en publicaciones no está disponible."

    def get_project_details(self, project_id: int):
        """Obtiene detalles completos de un proyecto por su ID, incluyendo AcademicMemberes y nodos."""
        print(f"   [Tool] Obteniendo detalles del proyecto ID: {project_id}...")
        return self.db.get_project_details(project_id)
        
    def list_all_wps(self):
        """Lista todos los Working Packages (WPs) disponibles."""
        print(f"   [Tool] Listando WPs...")
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, nombre FROM WPs")
        return [dict(row) for row in cursor.fetchall()]

    def send_message(self, message):
        try:
            response = self.chat.send_message(message)
            return response.text
        except Exception as e:
            return f"Ocurrió un error al procesar tu solicitud: {str(e)}"

    def close(self):
        self.db.close()
        # Note: Do NOT close semantic_engine here - it's a shared singleton
