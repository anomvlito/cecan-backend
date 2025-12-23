"""
General/Dashboard Routes for CECAN Platform
API endpoints for metrics, graph data, and dashboard statistics
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from api.routes.auth import get_current_user, User
from database.session import get_db
from services.analytics_service import analytics_service
from services.graph_service import build_graph_data
from services.ingestion_service import ingestion_service

router = APIRouter(tags=["Dashboard"])


@router.get("/metrics")
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns aggregated metrics for the Indicators dashboard"""
    return analytics_service.get_aggregated_metrics(db)


@router.get("/graph-data")
async def get_graph_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns the graph data (nodes and edges) for network visualization"""
    try:
        return build_graph_data(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")


@router.get("/impact-flow")
async def get_impact_flow(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns Sankey diagram data for Impact Flow visualization (WP -> Nodes)"""
    try:
        return analytics_service.get_impact_flow_graph(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching impact flow data: {str(e)}")


@router.post("/sync-external")
async def sync_external_data(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers an asynchronous synchronization with external APIs (OpenAlex, Semantic Scholar).
    """
    # Run sync in background to avoid HTTP timeout
    background_tasks.add_task(ingestion_service.run_weekly_sync, db)
    
    return {
        "message": "Sincronización externa iniciada en segundo plano", 
        "status": "processing"
    }

