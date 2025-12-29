import sqlite3
from typing import List, Dict, Any
from config import DB_PATH

class CecanDB:
    """
    Wrapper legacy para SQLite usado por el Agente y RAG.
    Permite la compatibilidad con los servicios antiguos mientras migramos a SQLAlchemy.
    """
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def search_projects(self, keyword: str) -> List[Dict[str, Any]]:
        """Busca proyectos (lógica portada del antiguo main.py)"""
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        query = f"%{keyword}%"
        # Nota: Ajusta esta consulta SQL según tus tablas reales 'proyectos'
        cursor.execute("""
            SELECT p.id, p.titulo, wp.nombre as wp_nombre
            FROM Proyectos p
            LEFT JOIN WPs wp ON p.wp_id = wp.id
            WHERE p.titulo LIKE ?
        """, (query,))
        return [dict(row) for row in cursor.fetchall()]

    def get_project_details(self, project_id: int) -> Dict[str, Any]:
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Proyectos WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else {}

    def get_all_projects_for_embedding(self):
        """Usado por rag_service para generar embeddings"""
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        # Asumiendo que quieres embedder títulos de proyectos
        cursor.execute("SELECT id, titulo FROM Proyectos")
        rows = cursor.fetchall()
        return [{"metadata": dict(r), "text": r['titulo']} for r in rows]
    
    def get_graph_data(self):
        """Retrieves all data necessary for the Vis.js graph visualization"""
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        nodes = []
        edges = []
        node_degrees = {}

        # 1. Investigadores (Migrated to academic_members)
        # Join with researcher_details to get more info
        cursor.execute("""
            SELECT 
                am.id, am.full_name, am.email, am.institution, am.wp_id,
                rd.category, rd.citaciones_totales, rd.indice_h, rd.url_foto, rd.orcid
            FROM academic_members am
            LEFT JOIN researcher_details rd ON am.id = rd.member_id
            WHERE am.member_type='researcher'
        """)
        
        researchers = cursor.fetchall()
        
        # Helper to get WPs for a member
        def get_member_wps(member_id):
            # Fetch from member_wps table
            cursor.execute("""
                SELECT w.id, w.nombre 
                FROM member_wps mw
                JOIN wps w ON mw.wp_id = w.id
                WHERE mw.member_id = ?
            """, (member_id,))
            return [{"id": row['id'], "nombre": row['nombre']} for row in cursor.fetchall()]

        for row in researchers:
            node_id = f"inv_{row['id']}"
            
            # Get WPs list
            wps_list = get_member_wps(row['id'])
            
            # Build rich metadata
            metadata = {
                "type": "Investigador",
                "nombre": row['full_name'],
                "email": row['email'],
                "institution": row['institution'],
                "wp": row['wp_id'], # Primary WP (legacy)
                "wps": wps_list,    # List of all WPs
                "category": row['category'],
                "citations": row['citaciones_totales'],
                "h_index": row['indice_h'],
                "orcid": row['orcid'],
                "photo": row['url_foto']
            }
            
            nodes.append({
                "id": node_id,
                "label": row['full_name'],
                "group": "investigator",
                "data": metadata,
                "color": "#e2e8f0",
                # Add image if available (Vis.js supports 'image' shape)
                # "shape": "circularImage" if row['url_foto'] else "dot",
                # "image": row['url_foto'] if row['url_foto'] else None
            })
            node_degrees[node_id] = 0

        # 2. WPs (lowercase)
        cursor.execute("SELECT id, nombre FROM wps")
        for row in cursor.fetchall():
            node_id = f"wp_{row['id']}"
            nodes.append({
                "id": node_id,
                "label": f"WP {row['id']}",
                "title": row['nombre'],
                "group": "wp",
                "data": {"type": "WP", "nombre": row['nombre']},
                "size": 50,
                "color": "#818cf8",
                "shape": "circle",
                "font": {"size": 18, "color": "#ffffff", "face": "Inter"}
            })
            node_degrees[node_id] = 0

        # 3. Nodos temáticos (lowercase)
        cursor.execute("SELECT id, nombre FROM nodos")
        for row in cursor.fetchall():
            node_id = f"nodo_{row['id']}"
            nodes.append({
                "id": node_id,
                "label": row['nombre'],
                "group": "nodo",
                "data": {"type": "Nodo", "nombre": row['nombre']},
                "color": "#67e8f9",
                "shape": "box"
            })
            node_degrees[node_id] = 0

        # 4. Proyectos (lowercase)
        cursor.execute("SELECT id, titulo, wp_id FROM proyectos")
        for row in cursor.fetchall():
            node_id = f"proj_{row['id']}"
            nodes.append({
                "id": node_id,
                "label": row['titulo'][:30] + "..." if len(row['titulo']) > 30 else row['titulo'],
                "title": row['titulo'],
                "group": "project",
                "data": {"type": "Proyecto", "nombre": row['titulo']},
                "color": "#6ee7b7"
            })
            node_degrees[node_id] = 0

            # Project-WP Edge
            if row['wp_id']:
                target_id = f"wp_{row['wp_id']}"
                edges.append({
                    "from": node_id,
                    "to": target_id,
                    "color": {"color": "#a5b4fc", "opacity": 0.5},
                    "width": 2
                })
                node_degrees[node_id] += 1
                node_degrees[target_id] += 1

        # 5. Edges: Proyecto - Investigador (lowercase)
        # Note: investigador_id column refers to academic_members.id now
        cursor.execute("SELECT proyecto_id, investigador_id, rol FROM proyecto_investigador")
        for row in cursor.fetchall():
            source_id = f"proj_{row['proyecto_id']}"
            target_id = f"inv_{row['investigador_id']}"
            is_responsable = row['rol'] == 'Responsable'

            edges.append({
                "from": source_id,
                "to": target_id,
                "color": {"color": "#fca5a5" if is_responsable else "#e2e8f0", "opacity": 0.8 if is_responsable else 0.3},
                "width": 2 if is_responsable else 1,
                # "hidden": True  <-- REMOVED TO FIX ORPHAN NODES
            })

            if source_id in node_degrees: node_degrees[source_id] += 1
            if target_id in node_degrees: node_degrees[target_id] += 1

        # 6. Edges: Proyecto - Nodo (lowercase)
        cursor.execute("SELECT proyecto_id, nodo_id FROM proyecto_nodo")
        for row in cursor.fetchall():
            source_id = f"proj_{row['proyecto_id']}"
            target_id = f"nodo_{row['nodo_id']}"

            edges.append({
                "from": source_id,
                "to": target_id,
                "color": {"color": "#22d3ee", "opacity": 0.4},
                "dashes": True
            })

            if source_id in node_degrees: node_degrees[source_id] += 1
            if target_id in node_degrees: node_degrees[target_id] += 1

        # Update node sizes based on degree centrality
        for node in nodes:
            degree = node_degrees.get(node['id'], 0)
            if node['group'] == 'investigator':
                node['value'] = degree
                node['title'] = f"{node['label']} (Conexiones: {degree})"
            elif node['group'] == 'project':
                node['value'] = degree * 2
            elif node['group'] == 'nodo':
                node['value'] = degree * 1.5

        return {"nodes": nodes, "edges": edges}

