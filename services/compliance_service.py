
import re
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.models import Publication

def run_full_audit(db: Session) -> None:
    """
    Realiza una auditoría completa de todas las publicaciones para verificar
    el cumplimiento de agradecimientos (FONDAP, CECAN).
    
    Actualiza:
    - has_funding_ack (Boolean)
    - anid_report_status (String: 'Compliant' | 'Review')
    """
    publications = db.query(Publication).all()
    
    # Patrones Regex
    patterns = {
        "FONDAP": r"FONDAP|1523A0004",
        "CECAN": r"CECAN|Centro para la Prevención",
        "ANID": r"ANID|Agencia Nacional"
    }
    
    for pub in publications:
        text = pub.contenido_texto if pub.contenido_texto else ""
        
        # Búsqueda de patrones
        has_fondap = bool(re.search(patterns["FONDAP"], text, re.IGNORECASE))
        has_cecan = bool(re.search(patterns["CECAN"], text, re.IGNORECASE))
        # has_anid = bool(re.search(patterns["ANID"], text, re.IGNORECASE)) # Buscado pero la regla de negocio usa FONDAP/CECAN
        
        # Regla de Negocio
        if has_fondap or has_cecan:
            pub.has_funding_ack = True
            pub.anid_report_status = "Compliant"
        else:
            pub.has_funding_ack = False
            pub.anid_report_status = "Review"
            
    # Commit en batch al final
    db.commit()

def reset_audit_status(db: Session) -> None:
    """
    Resetea el estado de auditoría de todas las publicaciones.
    Deja has_funding_ack en False y anid_report_status en 'Pending'.
    """
    db.query(Publication).update({
        Publication.has_funding_ack: False,
        Publication.anid_report_status: "Pending"
    })
    db.commit()

def get_compliance_report(db: Session) -> dict:
    """
    Retorna conteo total, conteo de compliant y porcentaje.
    """
    total = db.query(Publication).count()
    compliant_count = db.query(Publication).filter(Publication.has_funding_ack == True).count()
    
    percentage = (compliant_count / total * 100) if total > 0 else 0.0
    
    return {
        "total_publications": total,
        "compliant_publications": compliant_count,
        "compliance_percentage": round(percentage, 2)
    }

def audit_publication_by_id(pub_id: int, db: Session) -> None:
    """
    Realiza la auditoría para una sola publicación.
    """
    pub = db.query(Publication).filter(Publication.id == pub_id).first()
    if not pub:
        return

    patterns = {
        "FONDAP": r"FONDAP|1523A0004",
        "CECAN": r"CECAN|Centro para la Prevención",
        "ANID": r"ANID|Agencia Nacional"
    }

    text = pub.contenido_texto if pub.contenido_texto else ""
    
    has_fondap = bool(re.search(patterns["FONDAP"], text, re.IGNORECASE))
    has_cecan = bool(re.search(patterns["CECAN"], text, re.IGNORECASE))
    
    if has_fondap or has_cecan:
        pub.has_funding_ack = True
        pub.anid_report_status = "Compliant"
    else:
        pub.has_funding_ack = False
        pub.anid_report_status = "Review"
        
    db.commit()
