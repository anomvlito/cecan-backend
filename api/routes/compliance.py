"""
Compliance Audit Routes for CECAN Platform
API endpoints for "El Robot" compliance auditing system
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.session import get_db
from core.security import require_editor, require_viewer
from core.models import User
from services import compliance_service

router = APIRouter(prefix="/compliance", tags=["Compliance Audit"])


@router.post("/audit")
async def run_full_audit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Run complete compliance audit on all publications.
    Requires Editor role or higher.
    """
    result = compliance_service.run_full_audit(db)
    return {
        "message": f"Auditoría completada: {result['summary']['total_audited']} publicaciones procesadas",
        "summary": result["summary"]
    }


@router.get("/report")
async def get_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Get consolidated compliance report.
    Accessible to all authenticated users.
    """
    report = compliance_service.get_compliance_report(db)
    return report


@router.post("/audit/{publication_id}")
async def audit_single_publication(
    publication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Run compliance audit on a specific publication.
    Requires Editor role or higher.
    """
    result = compliance_service.audit_publication_by_id(publication_id, db)
    return {
        "message": "Auditoría completada",
        "publication_id": publication_id,
        "status": result["status"],
        "details": result
    }
