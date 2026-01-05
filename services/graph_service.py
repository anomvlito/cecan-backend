from sqlalchemy.orm import Session
from core.models import (
    AcademicMember, ResearcherDetails, Project,
    WorkPackage, Node, ProjectResearcher, ProjectNode
)

def build_graph_data(db: Session):
    """
    Builds the graph data (nodes and edges) for network visualization.
    Used by dashboard and public endpoints.
    """
    nodes = []
    edges = []
    node_degrees = {}

    def add_node(n_id, **kwargs):
        nodes.append({"id": n_id, **kwargs})
        node_degrees[n_id] = 0

    def add_edge(source, target, **kwargs):
        if source not in node_degrees: node_degrees[source] = 0
        if target not in node_degrees: node_degrees[target] = 0
        edges.append({"from": source, "to": target, **kwargs})
        node_degrees[source] += 1
        node_degrees[target] += 1

    # 1. Researchers
    researchers = db.query(AcademicMember, ResearcherDetails).outerjoin(
        ResearcherDetails, AcademicMember.id == ResearcherDetails.member_id
    ).filter(AcademicMember.member_type == 'researcher').all()

    for member, details in researchers:
        node_id = f"inv_{member.id}"
        
        # Calculate Impact Score for size
        from services.analytics_service import analytics_service
        impact_score = analytics_service.calculate_investigator_score(db, member.id)
        
        # Base size 25 + impact (max 45)
        node_size = 20 + (impact_score * 0.25)
        
        # WPs list (Updated to use 'name' instead of 'nombre')
        wps_list = [{"id": wp.id, "name": wp.name} for wp in member.wps]
        
        metadata = {
            "type": "Investigador",
            "name": member.full_name, # Renamed key for consistency, but frontend might expect 'nombre'
            "nombre": member.full_name, # Keep 'nombre' for frontend compatibility if needed
            "email": member.email,
            "institution": member.institution,
            "wp": member.wp_id,
            "wps": wps_list,
            "category": details.category if details else None,
            "citations": details.citaciones_totales if details else None,
            "h_index": details.indice_h if details else None,
            "photo": details.url_foto if details else None,
            "impact_score": impact_score,
            "orcid": details.orcid if details else None  # Add ORCID for badge display
        }
        
        add_node(
            node_id,
            label=member.full_name,
            group="investigator",
            data=metadata,
            color="#e2e8f0",
            size=node_size
        )

    # 2. WPs
    wps = db.query(WorkPackage).all()
    for wp in wps:
        node_id = f"wp_{wp.id}"
        add_node(
            node_id,
            label=f"WP {wp.id}",
            title=wp.name, # Renamed from nombre
            group="wp",
            data={"type": "WP", "nombre": wp.name, "name": wp.name},
            size=50,
            color="#818cf8",
            shape="circle",
            font={"size": 18, "color": "#ffffff", "face": "Inter"}
        )

    # 3. Nodes (Thematic Nodes)
    thematic_nodes = db.query(Node).all()
    for node in thematic_nodes:
        node_id = f"nodo_{node.id}"
        add_node(
            node_id,
            label=node.name, # Renamed from nombre
            group="nodo",
            data={"type": "Nodo", "nombre": node.name, "name": node.name},
            color="#67e8f9",
            shape="box"
        )

    # 4. Projects
    projects = db.query(Project).all()
    for proj in projects:
        node_id = f"proj_{proj.id}"
        # Renamed from titulo -> title
        label = proj.title[:30] + "..." if len(proj.title) > 30 else proj.title
        add_node(
            node_id,
            label=label,
            title=proj.title,
            group="project",
            data={"type": "Proyecto", "nombre": proj.title, "title": proj.title},
            color="#6ee7b7"
        )

        # Edge: Project -> WP
        if proj.wp_id:
            target_id = f"wp_{proj.wp_id}"
            add_edge(node_id, target_id, color={"color": "#a5b4fc", "opacity": 0.5}, width=2)
        
        # Edge: Project -> Researcher
        for pr in proj.researcher_connections:
            target_inv_id = f"inv_{pr.member_id}"
            is_responsable = pr.role == 'Responsable' # Renamed from rol
            add_edge(
                node_id, 
                target_inv_id,
                color={"color": "#fca5a5" if is_responsable else "#e2e8f0", "opacity": 0.8 if is_responsable else 0.3},
                width=2 if is_responsable else 1
            )
            
        # Edge: Project -> Node
        for pn in proj.node_connections:
            # Renamed from nodo_id -> node_id
            target_node_id = f"nodo_{pn.node_id}"
            add_edge(node_id, target_node_id, color={"color": "#a5f3fc", "opacity": 0.5}, width=1)

    return {"nodes": nodes, "edges": edges}
