from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from core.models import (
    AcademicMember, ResearcherDetails, Publication, Project,
    WorkPackage, Node, ProjectNode, ProjectOtherWP, IngestionAudit
)

class AnalyticsService:
    """Service for calculating metrics and generating analytics data."""

    def get_aggregated_metrics(self, db: Session) -> dict:
        """Returns aggregated metrics (publications, citations, h-index, investigators)."""
        from core.models import ExternalMetric

        # 1. Total publications
        total_pubs = db.query(func.count(Publication.id)).scalar()
        
        # 2. Total citations (Local + External)
        # Local from researcher_details (historical/manual)
        local_citations = db.query(func.sum(ResearcherDetails.citaciones_totales)).scalar() or 0
        
        # External from external_metrics (author level)
        # Sum of latest citation_count across all sources/members
        # Note: This is an approximation. In a production system we'd use a more sophisticated join.
        latest_external_citations = db.query(func.sum(ExternalMetric.value)).filter(
            ExternalMetric.metric_type == 'citation_count',
            ExternalMetric.member_id.isnot(None)
        ).scalar() or 0
        
        # 3. Average H-index (External preferred)
        # Current logic: Get latest recorded h_index in external_metrics per member
        ext_hindex = db.query(func.avg(ExternalMetric.value)).filter(
            ExternalMetric.metric_type == 'h_index',
            ExternalMetric.value > 0
        ).scalar()
        
        # Fallback to ResearcherDetails if no external h-index yet
        if not ext_hindex:
            avg_hindex = db.query(func.avg(ResearcherDetails.indice_h)).filter(
                ResearcherDetails.indice_h.isnot(None), 
                ResearcherDetails.indice_h > 0
            ).scalar() or 0
        else:
            avg_hindex = ext_hindex
        
        # 4. Total investigators
        total_investigators = db.query(func.count(AcademicMember.id)).filter(
            AcademicMember.member_type == 'researcher'
        ).scalar()
        
        return {
            "total_publicaciones": total_pubs,
            "total_citas": int(local_citations + latest_external_citations),
            "indice_h_promedio": round(avg_hindex, 1),
            "total_investigadores": total_investigators
        }

    def get_impact_flow_graph(self, db: Session) -> dict:
        """Returns Sankey diagram data for Impact Flow visualization (WP -> Nodes)."""
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
        
        # Helper to add node if not exists
        def ensure_node(name, color):
            if name not in wp_set and name not in node_set:
                nodes.append({"id": name, "nodeColor": color})
                
        # 1. Projects connecting WPs to Nodes
        results = (
            db.query(
                WorkPackage.id.label("wp_id"),
                WorkPackage.name.label("wp_name"), # Renamed from nombre
                Node.id.label("node_id"),
                Node.name.label("node_name") # Renamed from nombre
            )
            .select_from(Project)
            .join(WorkPackage, Project.wp_id == WorkPackage.id)
            .join(ProjectNode, Project.id == ProjectNode.project_id) # Renamed from proyecto_id
            .join(Node, ProjectNode.node_id == Node.id) # Renamed from nodo_id
            .all()
        )
        
        for wp_id, wp_name, node_id, node_name in results:
            if not wp_name or not node_name: continue
            
            # WPs
            if wp_name not in wp_set:
                ensure_node(wp_name, WP_COLORS.get(wp_id, "#718096"))
                wp_set.add(wp_name)
            
            # Nodes
            if node_name not in node_set:
                ensure_node(node_name, NODE_COLOR)
                node_set.add(node_name)
            
            link_key = (wp_name, node_name)
            links_dict[link_key] = links_dict.get(link_key, 0) + 1

        # 2. WP -> WP Collaboration (ProjectOtherWP)
        # Assuming ProjectOtherWP connects a Project (which has a WP) to another WP (OtherWP)
        
        # Aliased WPs for join
        WP1 = aliased(WorkPackage)
        WP2 = aliased(WorkPackage)
        
        collab_results = (
            db.query(
                WP1.id.label("source_id"),
                WP1.name.label("source_name"), # Renamed
                WP2.id.label("target_id"), 
                WP2.name.label("target_name"), # Renamed
                func.count(Project.id).label("count")
            )
            .select_from(Project)
            .join(WP1, Project.wp_id == WP1.id)
            .join(ProjectOtherWP, Project.id == ProjectOtherWP.project_id) # Renamed from proyecto_id
            .join(WP2, ProjectOtherWP.wp_id == WP2.id)
            .filter(Project.wp_id != ProjectOtherWP.wp_id) # Avoid self-loops if any
            .group_by(WP1.id, WP2.id, WP1.name, WP2.name) # Added name to group by
            .all()
        )
        
        for src_id, src_name, tgt_id, tgt_name, count in collab_results:
            if src_name not in wp_set:
                ensure_node(src_name, WP_COLORS.get(src_id, "#718096"))
                wp_set.add(src_name)
            
            if tgt_name not in wp_set:
                ensure_node(tgt_name, WP_COLORS.get(tgt_id, "#718096"))
                wp_set.add(tgt_name)
                
            link_key = (src_name, tgt_name)
            links_dict[link_key] = links_dict.get(link_key, 0) + count

        # Format links
        links = [
            {"source": src, "target": tgt, "value": val}
            for (src, tgt), val in links_dict.items()
        ]
        
        return {"nodes": nodes, "links": links}

    def calculate_investigator_score(self, db: Session, member_id: int) -> float:
        """
        Calculates an impact score (0-100) for a researcher.
        Ponders: Citations (40%), Projects (40%), Connectivity (20%).
        """
        from core.models import ExternalMetric, ProjectResearcher, ProjectNode, Project
        
        # 1. Citations Score (40%)
        # Get latest citation count from external metrics
        citations = db.query(func.sum(ExternalMetric.value)).filter(
            ExternalMetric.member_id == member_id,
            ExternalMetric.metric_type == 'citation_count'
        ).scalar() or 0
        
        # Normalize against a high-impact threshold (e.g., 1000 citations = max points)
        # Or more dynamically, against the max in the center
        max_citations = db.query(func.max(ExternalMetric.value)).filter(
            ExternalMetric.metric_type == 'citation_count'
        ).scalar() or 100
        
        cit_score = min(100, (citations / max_citations) * 100) * 0.4

        # 2. Projects Score (40%)
        # Count of projects this researcher is involved in
        proj_count = db.query(func.count(ProjectResearcher.id)).filter(
            ProjectResearcher.member_id == member_id
        ).scalar() or 0
        
        # Threshold: 5 projects = max points
        proj_score = min(100, (proj_count / 5) * 100) * 0.4

        # 3. Connectivity/Centrality (20%)
        # Count of unique WPs and Nodes touched via projects
        # Updated joins to use new English FKs (project_id, node_id)
        nodes_touched = db.query(func.count(func.distinct(ProjectNode.node_id))).join(
            Project, Project.id == ProjectNode.project_id
        ).join(
            ProjectResearcher, Project.id == ProjectResearcher.project_id
        ).filter(ProjectResearcher.member_id == member_id).scalar() or 0
        
        # Threshold: 4 nodes = max points
        conn_score = min(100, (nodes_touched / 4) * 100) * 0.2

        total_score = cit_score + proj_score + conn_score
        return round(total_score, 1)

# Global instance
analytics_service = AnalyticsService()
