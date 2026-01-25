import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

class CecanDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def search_projects(self, keyword):
        # Expanded search query
        query = """
            SELECT DISTINCT p.id, p.titulo, w.nombre as wp_nombre
            FROM Proyectos p
            JOIN WPs w ON p.wp_id = w.id
            LEFT JOIN Proyecto_Investigador pi ON p.id = pi.proyecto_id
            LEFT JOIN Investigadores i ON pi.investigador_id = i.id
            LEFT JOIN Proyecto_Nodo pn ON p.id = pn.proyecto_id
            LEFT JOIN Nodos n ON pn.nodo_id = n.id
            WHERE 
                p.titulo LIKE ? OR
                i.nombre LIKE ? OR
                n.nombre LIKE ? OR
                w.nombre LIKE ?
        """
        search_term = f'%{keyword}%'
        cursor = self.conn.cursor()
        cursor.execute(query, (search_term, search_term, search_term, search_term))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_projects_for_embedding(self):
        """Retrieves all projects with their full context for embedding generation."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM Proyectos")
        project_ids = [row[0] for row in cursor.fetchall()]
        
        projects = []
        for pid in project_ids:
            details = self._get_project_data_raw(pid)
            if not details: continue

            # Construct a single string representation
            text_parts = [
                f"Título: {details['titulo']}",
                f"WP: {details['wp_nombre']}",
                f"Nodos: {', '.join(details['nodos'])}"
            ]
            investigators = [f"{inv['nombre']} ({inv['rol']})" for inv in details['investigadores']]
            text_parts.append(f"Investigadores: {', '.join(investigators)}")
            
            full_text = ". ".join(text_parts)
            projects.append({
                "id": pid,
                "text": full_text,
                "metadata": details
            })
        return projects

    def _get_project_data_raw(self, project_id):
        """Internal method to get project data as a dictionary."""
        cursor = self.conn.cursor()
        
        # 1. Datos del proyecto y WP
        cursor.execute("""
            SELECT p.titulo, w.nombre as wp_nombre 
            FROM Proyectos p 
            JOIN WPs w ON p.wp_id = w.id 
            WHERE p.id = ?
        """, (project_id,))
        proj = cursor.fetchone()
        
        if not proj: return None
        
        # 2. Investigadores y sus roles
        cursor.execute("""
            SELECT i.id, i.nombre, pi.rol 
            FROM Proyecto_Investigador pi
            JOIN Investigadores i ON pi.investigador_id = i.id
            WHERE pi.proyecto_id = ?
        """, (project_id,))
        investigadores_rows = cursor.fetchall()
        investigadores_list = [{"id": row['id'], "nombre": row['nombre'], "rol": row['rol']} for row in investigadores_rows]

        # 3. Nodos temáticos
        cursor.execute("""
            SELECT n.nombre 
            FROM Proyecto_Nodo pn
            JOIN Nodos n ON pn.nodo_id = n.id
            WHERE pn.proyecto_id = ?
        """, (project_id,))
        nodos = [row['nombre'] for row in cursor.fetchall()]

        # 4. Proyectos Relacionados por Investigadores compartidos
        related_projects = []
        if investigadores_rows:
            inv_ids = [row['id'] for row in investigadores_rows]
            if inv_ids:
                placeholders = ','.join(['?'] * len(inv_ids))
                # Excluir el proyecto actual
                query_related = f"""
                    SELECT DISTINCT p.titulo 
                    FROM Proyectos p
                    JOIN Proyecto_Investigador pi ON p.id = pi.proyecto_id
                    WHERE pi.investigador_id IN ({placeholders}) AND p.id != ?
                    LIMIT 5
                """
                params = list(inv_ids)
                params.append(project_id)
                
                cursor.execute(query_related, params)
                related_projects = [row['titulo'] for row in cursor.fetchall()]
        
        return {
            "titulo": proj['titulo'],
            "wp_nombre": proj['wp_nombre'],
            "investigadores": investigadores_list,
            "nodos": nodos,
            "related_projects": related_projects
        }

    def get_graph_data(self):
        """Retrieves all data necessary for the Vis.js graph visualization."""
        cursor = self.conn.cursor()
        nodes = []
        edges = []
        
        # Helper to track node degrees for sizing
        node_degrees = {}

        # 1. Investigadores (Nodes)
        cursor.execute("SELECT id, nombre FROM Investigadores")
        for row in cursor.fetchall():
            node_id = f"inv_{row['id']}"
            nodes.append({
                "id": node_id, 
                "label": row['nombre'], 
                "group": "investigator", 
                "data": {"type": "Investigador", "nombre": row['nombre']},
                "color": "#cbd5e1" # Slate 300 (default hidden/low priority)
            })
            node_degrees[node_id] = 0

        # 2. WPs (Nodes) - High visual hierarchy
        cursor.execute("SELECT id, nombre FROM WPs")
        for row in cursor.fetchall():
            node_id = f"wp_{row['id']}"
            nodes.append({
                "id": node_id, 
                "label": f"WP {row['id']}", 
                "title": row['nombre'], # Tooltip
                "group": "wp", 
                "data": {"type": "WP", "nombre": row['nombre']},
                "size": 40,
                "color": "#4f46e5", # Indigo 600
                "font": {"size": 16, "color": "#ffffff", "face": "Inter"}
            })
            node_degrees[node_id] = 0
            
        # 3. Nodos (Temas Transversales) (Nodes)
        cursor.execute("SELECT id, nombre FROM Nodos")
        for row in cursor.fetchall():
            node_id = f"nodo_{row['id']}"
            nodes.append({
                "id": node_id, 
                "label": row['nombre'], 
                "group": "nodo", 
                "data": {"type": "Nodo", "nombre": row['nombre']},
                "color": "#0891b2", # Cyan 600
                "shape": "box"
            })
            node_degrees[node_id] = 0
        
        # 4. Proyectos (Nodes)
        cursor.execute("SELECT id, titulo, wp_id FROM Proyectos")
        for row in cursor.fetchall():
            node_id = f"proj_{row['id']}"
            nodes.append({
                "id": node_id, 
                "label": row['titulo'][:30] + "..." if len(row['titulo']) > 30 else row['titulo'], 
                "title": row['titulo'],
                "group": "project", 
                "data": {"type": "Proyecto", "nombre": row['titulo']},
                "color": "#e2e8f0" # Slate 200
            })
            node_degrees[node_id] = 0
            
            # Project-WP Edge (Eje Principal)
            if row['wp_id']:
                target_id = f"wp_{row['wp_id']}"
                edges.append({
                    "from": node_id, 
                    "to": target_id, 
                    "color": {"color": "#a5b4fc", "opacity": 0.5}, # Indigo 300
                    "width": 2
                })
                node_degrees[node_id] += 1
                node_degrees[target_id] += 1

        # 5. Edges: Proyecto - Investigador
        cursor.execute("SELECT proyecto_id, investigador_id, rol FROM Proyecto_Investigador")
        for row in cursor.fetchall():
            source_id = f"proj_{row['proyecto_id']}"
            target_id = f"inv_{row['investigador_id']}"
            is_responsable = row['rol'] == 'Responsable'
            
            edges.append({
                "from": source_id, 
                "to": target_id, 
                "color": {"color": "#fca5a5" if is_responsable else "#e2e8f0", "opacity": 0.8 if is_responsable else 0.3}, 
                "width": 2 if is_responsable else 1,
                "hidden": True # Hidden by default for Overview Mode
            })
            
            if source_id in node_degrees: node_degrees[source_id] += 1
            if target_id in node_degrees: node_degrees[target_id] += 1

        # 6. Edges: Proyecto - Nodo
        cursor.execute("SELECT proyecto_id, nodo_id FROM Proyecto_Nodo")
        for row in cursor.fetchall():
            source_id = f"proj_{row['proyecto_id']}"
            target_id = f"nodo_{row['nodo_id']}"
            
            edges.append({
                "from": source_id, 
                "to": target_id, 
                "color": {"color": "#22d3ee", "opacity": 0.4}, # Cyan 400
                "dashes": True
            })
            
            if source_id in node_degrees: node_degrees[source_id] += 1
            if target_id in node_degrees: node_degrees[target_id] += 1

        # Update node sizes based on degree centrality
        for node in nodes:
            degree = node_degrees.get(node['id'], 0)
            # Base size + degree factor
            if node['group'] == 'investigator':
                node['value'] = degree # Vis.js uses 'value' for scaling
                node['title'] = f"{node['label']} (Conexiones: {degree})"
            elif node['group'] == 'project':
                node['value'] = degree * 2
            elif node['group'] == 'nodo':
                node['value'] = degree * 1.5

        return {"nodes": nodes, "edges": edges}

    def get_project_details(self, project_id):
        data = self._get_project_data_raw(project_id)
        
        if not data: return "Proyecto no encontrado."
        
        investigadores_str = [f"{inv['nombre']} ({inv['rol']})" for inv in data['investigadores']]
        
        # Formateamos un texto rico para que el LLM lo procese
        return f"""
        DATOS DEL PROYECTO (ID: {project_id}):
        - Título: {data['titulo']}
        - Eje Principal: {data['wp_nombre']}
        - Equipo: {', '.join(investigadores_str)}
        - Temas Transversales (Nodos): {', '.join(data['nodos']) if data['nodos'] else 'Ninguno'}
        - Conexiones del Cluster (Otros proyectos de este equipo): {', '.join(data['related_projects']) if data['related_projects'] else 'Ninguno'}
        """

def main():
    db = CecanDB()
    db.connect()
    
    print("--- CECAN Agent DB Interface ---")
    
    # Example: List all projects
    print("\nTotal Projects:")
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Proyectos")
    print(cursor.fetchone()[0])

    # Example: Search
    keyword = "cancer"
    print(f"\nSearching for '{keyword}':")
    results = db.search_projects(keyword)
    for p in results:
        print(f"- [{p['id']}] {p['titulo']} ({p['wp_nombre']})")
        
    if results:
        first_id = results[0]['id']
        print(f"\nDetails for Project ID {first_id}:")
        details = db.get_project_details(first_id)
        print(f"Title: {details['titulo']}")
        print(f"WP: {details['wp_nombre']}")
        print("Investigators:")
        for inv in details['investigadores']:
            print(f"  - {inv['nombre']} ({inv['rol']})")
        print("Nodes:", ", ".join(details['nodos']))

    db.close()

if __name__ == "__main__":
    main()
