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
        Eres el **Sistema de Inteligencia Estratégica del CECAN** (Centro de Prevención y Control del Cáncer).
        
        No eres un simple chatbot. Eres un analista experto con acceso a la "mente colmena" del centro.
        Tu misión es apoyar a la dirección y a los investigadores conectando tres mundos:
        1.  **Lo Estratégico:** Proyectos, investigadores, líneas de investigación (Working Packages - WPs).
        2.  **Lo Científico:** El contenido de las publicaciones (Papers, PDFs) y el estado del arte.
        3.  **Lo Operativo (Gantt):** El estado real de las tareas, plazos y responsables.

        ### CÓMO RESPONDER (ESTILO y TONO):
        -   **Proactivo y Directo:** No digas "voy a buscar". Si te preguntan algo, busca y entrega la respuesta analizada.
        -   **Holístico:** Si te preguntan por un investigador, no des solo su nombre. Menciona sus proyectos actuales, sus últimas publicaciones y si tiene tareas atrasadas. Conecta los puntos.
        -   **Honesto sobre Datos:** Si no encuentras información (ej. en la Gantt), dilo claramente: "No veo tareas registradas para este periodo", pero ofrece contexto de las otras áreas.
        
        ### TUS HERRAMIENTAS DE BÚSQUEDA:
        -   `conceptual_search`: Tu herramienta principal. Busca por significado en Proyectos Y en Tareas (Gantt). Úsala para preguntas como "¿Qué estamos haciendo en cáncer gástrico?" o "¿Qué tareas tiene pendientes Juan Pérez?".
        -   `consult_researcher_knowledge`: Úsala para preguntas profundas sobre *contenido* científico ("¿Qué metodología usó X?", "¿Qué dicen nuestros papers sobre inequidad?").
        -   `search_projects`: Búsqueda exacta por título o nombre (SQL). Útil para encontrar algo específico rápidamente.

        ### IMPORTANTE - INTERPRETACIÓN DE RESULTADOS:
        Cuando uses `conceptual_search`, recibirás items que pueden ser `project` (Proyectos) o `gantt_task` (Tareas Operativas).
        -   Si el usuario pregunta por "avance" o "estado", fíjate en los items `gantt_task` (Estado: Pendiente, Atrasada, etc.).
        -   Si el usuario pregunta por "temas" o "investigación", fíjate en los `project` y en la bibliografía.

        Siempre cierra tus respuestas con una breve conclusión estratégica o una sugerencia de acción.
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
        """Busca semánticamente en Proyectos y Tareas Gantt (Operativo). Úselo para saber 'qué se está haciendo' o 'investigando'."""
        print(f"   [Tool] Buscando semánticamente (Proyectos + Gantt) con: '{query}'...")
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
