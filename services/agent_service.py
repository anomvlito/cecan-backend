import os
from dotenv import load_dotenv

load_dotenv()
from collections.abc import Iterable
import sys
import threading

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from database.session import get_session
from core.models import Project, WorkPackage, AcademicMember, Node
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
        session = get_session()
        try:
            # Simplify search: search in Project title
            # In a real scenario, this would be more complex joins.
            # Mirroring legacy wrapper logic: searches in title, researcher name, wp name, node name
            
            projects = (
                session.query(Project)
                .outerjoin(WorkPackage, Project.wp_id == WorkPackage.id)
                .filter(
                    or_(
                        Project.titulo.ilike(f"%{keyword}%"),
                        WorkPackage.nombre.ilike(f"%{keyword}%")
                        # Add other fields if needed, simplified for ORM
                    )
                )
                .all()
            )
            
            results = []
            for p in projects:
                results.append({
                    "id": p.id,
                    "title": p.titulo,
                    "wp": p.wp.nombre if p.wp else None
                })
            return results
        finally:
            session.close()

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
        session = get_session()
        try:
            p = session.query(Project).filter(Project.id == project_id).first()
            if not p:
                return f"Proyecto {project_id} no encontrado."
            
            details = {
                "id": p.id,
                "titulo": p.titulo,
                "wp": p.wp.nombre if p.wp else "Sin WP",
                "descripcion": getattr(p, 'descripcion', "Sin descripción"), # Assuming description exists or not?
                "estado": getattr(p, 'estado', "Desconocido"),
                "fecha_inicio": getattr(p, 'fecha_inicio', None),
                "fecha_termino": getattr(p, 'fecha_termino', None),
                "investigadores": [
                    {"nombre": pr.member.full_name, "rol": pr.rol} 
                    for pr in p.researcher_connections
                ],
                "nodos": [pn.node.nombre for pn in p.node_connections]
            }
            return details
        finally:
            session.close()
        
    def list_all_wps(self):
        """Lista todos los Working Packages (WPs) disponibles."""
        print(f"   [Tool] Listando WPs...")
        session = get_session()
        try:
            wps = session.query(WorkPackage).all()
            return [{"id": wp.id, "nombre": wp.nombre} for wp in wps]
        finally:
            session.close()

    def send_message(self, message):
        try:
            response = self.chat.send_message(message)
            return response.text
        except Exception as e:
            return f"Ocurrió un error al procesar tu solicitud: {str(e)}"

    def detect_research_gaps(self, db: Session):
        """
        Strategic analysis: crosses WPs with Nodes to detect gaps (no projects/pubs).
        Saves findings to ResearchOpportunity table.
        """
        from core.models import ResearchOpportunity, ProjectNode, Project, Node, WorkPackage
        
        print("   [IA] Iniciando análisis de brechas estratégicas...")
        
        wps = db.query(WorkPackage).all()
        nodes = db.query(Node).all()
        
        gaps_found = 0
        
        for wp in wps:
            for node in nodes:
                # Check coverage: Is there any project connecting this WP and this Node?
                exists = db.query(Project).join(ProjectNode).filter(
                    Project.wp_id == wp.id,
                    ProjectNode.nodo_id == node.id
                ).first()
                
                if not exists:
                    # Potential Gap! Let's ask Gemini to frame it
                    prompt = f"""
                    Como Estratega del CECAN, analiza esta brecha de investigación:
                    - Work Package: {wp.nombre}
                    - Nodo Temático: {node.nombre}
                    
                    No hay proyectos activos que conecten este grupo de trabajo con este tipo de cáncer/tema.
                    Genera una breve descripción del 'gap' y una 'línea de investigación sugerida' que sea innovadora.
                    
                    Formato:
                    GAP: <descripción>
                    LINEA: <sugerencia>
                    """
                    
                    try:
                        response = self.model.generate_content(prompt)
                        text = response.text
                        
                        # Simple parsing
                        gap_desc = ""
                        suggested = ""
                        
                        if "GAP:" in text and "LINEA:" in text:
                            parts = text.split("LINEA:")
                            gap_desc = parts[0].replace("GAP:", "").strip()
                            suggested = parts[1].strip()
                        else:
                            gap_desc = f"Falta de integración entre {wp.nombre} y {node.nombre}."
                            suggested = text.strip()

                        # Persistence (Upsert logical)
                        existing_gap = db.query(ResearchOpportunity).filter(
                            ResearchOpportunity.target_wp_id == wp.id,
                            ResearchOpportunity.target_node_id == node.id
                        ).first()
                        
                        if not existing_gap:
                            new_op = ResearchOpportunity(
                                target_wp_id=wp.id,
                                target_node_id=node.id,
                                gap_description=gap_desc,
                                suggested_line=suggested,
                                impact_potential=0.5 # Default
                            )
                            db.add(new_op)
                            gaps_found += 1
                        
                    except Exception as e:
                        print(f"      [Error] Gemini falló para {wp.nombre}/{node.nombre}: {e}")
        
        db.commit()
        print(f"   [IA] Análisis completado. {gaps_found} nuevas oportunidades detectadas.")
        return {"status": "success", "gaps_detected": gaps_found}

    def close(self):
        # self.db.close() # Removed
        # Note: Do NOT close semantic_engine here - it's a shared singleton
        pass
