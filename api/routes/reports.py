from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
import io
from datetime import datetime

from database.session import get_db
from core.models import WorkPackage, Project, AcademicMember, Publication, ComplianceStatus
from api.routes.auth import require_editor, User, get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/summary")
async def get_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get summary of projects and members per WP.
    """
    wps = db.query(WorkPackage).all()
    summary = []
    
    for wp in wps:
        project_count = db.query(func.count(Project.id)).filter(Project.wp_id == wp.id).scalar()
        member_count = db.query(func.count(AcademicMember.id)).filter(AcademicMember.wp_id == wp.id).scalar()
        
        summary.append({
            "wp_id": wp.id,
            "wp_name": wp.nombre,
            "project_count": project_count,
            "member_count": member_count
        })
        
    return summary

@router.get("/compliance/export")
async def export_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """
    Export compliance report to Excel.
    Requires Editor role.
    """
    try:
        # Query publications
        pubs = db.query(Publication).all()
        
        data = []
        for pub in pubs:
            data.append({
                "ID": pub.id,
                "Título": pub.titulo,
                "Fecha": pub.fecha,
                "Categoría": pub.categoria,
                "Estado Reporte ANID": pub.anid_report_status.value if pub.anid_report_status else "N/A",
                "Afiliación Válida": "Sí" if pub.has_valid_affiliation else "No",
                "Agradecimiento Funding": "Sí" if pub.has_funding_ack else "No",
                "Notas Auditoría": pub.audit_notes or "",
                "Última Auditoría": pub.last_audit_date.strftime("%Y-%m-%d %H:%M") if pub.last_audit_date else "N/A"
            })
            
        df = pd.DataFrame(data)
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Compliance Report')
            
        output.seek(0)
        
        filename = f"cecan_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating export: {str(e)}")
