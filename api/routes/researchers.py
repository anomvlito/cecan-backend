from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import threading
from typing import List

from core.security import require_editor, get_current_user
from core.models import User
from database.session import get_db
from core.models import AcademicMember, ResearcherDetails, ProjectResearcher, ResearcherPublication
from services import scraper_service, matching_service

router = APIRouter(prefix="/researchers", tags=["Researchers"])


@router.get("")
async def get_researchers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all researchers/staff members"""
    # Query AcademicMember joined with ResearcherDetails
    researchers = (
        db.query(AcademicMember, ResearcherDetails)
        .join(ResearcherDetails, AcademicMember.id == ResearcherDetails.member_id)
        .filter(AcademicMember.member_type == "researcher")
        .all()
    )
    
    result = []
    for member, details in researchers:
        # Count active projects
        active_projects_count = (
            db.query(func.count(ProjectResearcher.id))
            .filter(ProjectResearcher.member_id == member.id)
            .scalar()
        )
        
        # Count recent publications
        recent_pubs_count = (
            db.query(func.count(ResearcherPublication.id))
            .filter(ResearcherPublication.member_id == member.id)
            .scalar()
        )
        
        result.append({
            "id": member.id,
            "nombre": member.full_name,
            "cargo_oficial": details.category,
            "url_foto": details.url_foto,
            "active_projects": active_projects_count,
            "citaciones_totales": details.citaciones_totales,
            "indice_h": details.indice_h,
            "works_count": details.works_count,
            "i10_index": details.i10_index,
            "publicaciones_recientes": recent_pubs_count,
            "is_auditable": details.is_auditable,
            "last_openalex_sync": details.last_openalex_sync
        })
    
    return result


@router.post("/sync-openalex")
async def sync_openalex_metrics(
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Sincroniza métricas de OpenAlex para investigadores con ORCID.
    
    - **force_refresh**: Si es True, actualiza todos los investigadores.
                        Si es False, solo actualiza los que nunca se sincronizaron
                        o hace más de 30 días.
    
    Requiere rol Editor o superior.
    """
    from services.openalex_service import sync_all_researchers
    
    result = sync_all_researchers(db, force_refresh)
    return result


@router.post("/sync")
async def sync_staff(
    current_user: User = Depends(require_editor)
):
    """
    Synchronize staff data from external sources.
    Requires Editor role.
    """
    thread = threading.Thread(target=scraper_service.sync_staff_data)
    thread.start()
    
    return {
        "status": "started",
        "message": "Staff synchronization started in background"
    }


@router.post("/match")
async def run_matching(
    current_user: User = Depends(require_editor)
):
    """
    Run researcher-publication matching algorithm.
    Requires Editor role.
    """
    thread = threading.Thread(target=matching_service.match_researchers)
    thread.start()
    
    return {
        "status": "started",
        "message": "Matching process started in background"
    }
