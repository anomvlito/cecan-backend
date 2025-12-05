"""
General/Dashboard Routes for CECAN Platform
API endpoints for metrics, graph data, and dashboard statistics
"""

from fastapi import APIRouter, Depends
import sqlite3

from api.routes.auth import get_current_user, User
from config import DB_PATH
from database.legacy_wrapper import CecanDB

router = APIRouter(tags=["Dashboard"])


@router.get("/metrics")
async def get_metrics(current_user: User = Depends(get_current_user)):
    """Returns aggregated metrics for the Indicators dashboard"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total publications
    cursor.execute("SELECT COUNT(*) as total FROM publicaciones")
    total_pubs = cursor.fetchone()['total']
    
    # Total citations
    cursor.execute("SELECT SUM(citaciones_totales) as total FROM researcher_details")
    total_citations = cursor.fetchone()['total'] or 0
    
    # Average H-index
    cursor.execute("SELECT AVG(indice_h) as avg FROM researcher_details WHERE indice_h IS NOT NULL AND indice_h > 0")
    avg_hindex = cursor.fetchone()['avg'] or 0
    
    # Total investigators
    cursor.execute("SELECT COUNT(*) as total FROM academic_members WHERE member_type='researcher'")
    total_investigators = cursor.fetchone()['total']
    
    conn.close()
    
    return {
        "total_publicaciones": total_pubs,
        "total_citas": int(total_citations),
        "indice_h_promedio": round(avg_hindex, 1),
        "total_investigadores": total_investigators
    }


@router.get("/graph-data")
async def get_graph_data(current_user: User = Depends(get_current_user)):
    """Returns the graph data (nodes and edges) for network visualization"""
    db = CecanDB()
    try:
        db.connect()
        data = db.get_graph_data()
        return data
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")
    finally:
        db.close()


def get_impact_flow_data():
    """
    Build Sankey diagram data showing flow from WPs to Cancer Nodes via Projects.
    Returns nodes (WPs + Nodes) and links (WP -> Node with project count as value).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Color palettes
    WP_COLORS = {
        1: "#4299E1",  # Blue
        2: "#48BB78",  # Green
        3: "#ECC94B",  # Yellow
        4: "#ED8936",  # Orange
        5: "#9F7AEA",  # Purple
    }
    NODE_COLOR = "#E53E3E"  # Red for cancer nodes
    
    nodes = []
    links_dict = {}  # (source, target) -> count
    wp_set = set()
    node_set = set()
    
    # Query projects with their WP and connected nodes
    cursor.execute("""
        SELECT 
            p.id as project_id,
            p.titulo as project_title,
            w.id as wp_id,
            w.nombre as wp_name,
            n.id as node_id,
            n.nombre as node_name
        FROM proyectos p
        LEFT JOIN wps w ON p.wp_id = w.id
        LEFT JOIN proyecto_nodo pn ON p.id = pn.proyecto_id
        LEFT JOIN nodos n ON pn.nodo_id = n.id
        WHERE w.id IS NOT NULL
    """)
    
    rows = cursor.fetchall()
    
    for row in rows:
        wp_id = row['wp_id']
        wp_name = row['wp_name']
        node_id = row['node_id']
        node_name = row['node_name']
        
        # Track unique WPs - use name for display
        if wp_id and wp_name:
            wp_key = wp_name  # Use readable name as ID
            if wp_key not in wp_set:
                wp_set.add(wp_key)
                nodes.append({
                    "id": wp_key,
                    "nodeColor": WP_COLORS.get(wp_id, "#718096")
                })
        
        # Track unique Nodes (Cancer Types) - use name for display
        if node_id and node_name:
            node_key = node_name  # Use readable name as ID
            if node_key not in node_set:
                node_set.add(node_key)
                nodes.append({
                    "id": node_key,
                    "nodeColor": NODE_COLOR
                })
            
            # Count link (WP -> Node)
            link_key = (wp_key, node_key)
            links_dict[link_key] = links_dict.get(link_key, 0) + 1

    
    # Also check for WP->WP collaboration via proyecto_otrowp
    cursor.execute("""
        SELECT 
            w1.id as source_wp_id,
            w1.nombre as source_wp_name,
            w2.id as target_wp_id,
            w2.nombre as target_wp_name,
            COUNT(*) as count
        FROM proyectos p
        JOIN proyecto_otrowp pow ON p.id = pow.proyecto_id
        JOIN wps w1 ON p.wp_id = w1.id
        JOIN wps w2 ON pow.wp_id = w2.id
        WHERE p.wp_id IS NOT NULL AND pow.wp_id IS NOT NULL AND p.wp_id != pow.wp_id
        GROUP BY p.wp_id, pow.wp_id
    """)
    
    for row in cursor.fetchall():
        source_key = row['source_wp_name']
        target_key = row['target_wp_name']
        
        # Ensure both WPs are in nodes list
        if source_key not in wp_set:
            wp_set.add(source_key)
            nodes.append({
                "id": source_key,
                "nodeColor": WP_COLORS.get(row['source_wp_id'], "#718096")
            })
        if target_key not in wp_set:
            wp_set.add(target_key)
            nodes.append({
                "id": target_key,
                "nodeColor": WP_COLORS.get(row['target_wp_id'], "#718096")
            })
        
        link_key = (source_key, target_key)
        links_dict[link_key] = links_dict.get(link_key, 0) + row['count']
    
    conn.close()
    
    # Convert links dict to list
    links = [
        {"source": src, "target": tgt, "value": val}
        for (src, tgt), val in links_dict.items()
    ]
    
    return {"nodes": nodes, "links": links}


@router.get("/impact-flow")
async def get_impact_flow(current_user: User = Depends(get_current_user)):
    """Returns Sankey diagram data for Impact Flow visualization (WP -> Nodes)"""
    from fastapi import HTTPException
    try:
        data = get_impact_flow_data()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching impact flow data: {str(e)}")

