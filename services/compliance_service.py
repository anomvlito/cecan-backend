"""
Compliance Audit System - "El Robot"
Automated validation of business rules for ANID reporting compliance.
"""

import re
from typing import Dict, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import Publication, ComplianceStatus


# ===========================
# COMPLIANCE RULES CONFIGURATION
# ===========================

# Affiliation patterns to search for in publications
AFFILIATION_PATTERNS = [
    r"Center for Cancer Prevention",
    r"Centro de Prevención del Cáncer",
    r"CECAN",
    r"Pontificia Universidad Católica de Chile",
    r"UC Chile",
    r"Facultad de Medicina UC"
]

# Funding acknowledgment patterns
FUNDING_PATTERNS = [
    r"FONDAP\s*1?52220002",  # Main FONDAP code
    r"FONDAP\s*15220002",
    r"ANID",
    r"Agencia Nacional de Investigación y Desarrollo"
]


# ===========================
# CORE VALIDATION FUNCTIONS
# ===========================

def validate_affiliation(text: str) -> Tuple[bool, List[str]]:
    """
    Check if publication text contains valid CECAN affiliation.
    
    Args:
        text: Full publication text
    
    Returns:
        Tuple of (has_valid_affiliation, list of found patterns)
    """
    if not text:
        return False, []
    
    found_patterns = []
    text_lower = text.lower()
    
    for pattern in AFFILIATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found_patterns.append(pattern)
    
    has_valid = len(found_patterns) > 0
    return has_valid, found_patterns


def validate_funding_acknowledgment(text: str) -> Tuple[bool, List[str]]:
    """
    Check if publication text contains funding acknowledgment.
    
    Args:
        text: Full publication text
    
    Returns:
        Tuple of (has_funding_ack, list of found patterns)
    """
    if not text:
        return False, []
    
    found_patterns = []
    
    for pattern in FUNDING_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found_patterns.append(pattern)
    
    has_funding = len(found_patterns) > 0
    return has_funding, found_patterns


def determine_compliance_status(has_affiliation: bool, has_funding: bool) -> ComplianceStatus:
    """
    Determine overall compliance status based on validation results.
    
    Rules:
    - OK: Has both affiliation and funding acknowledgment
    - WARNING: Has affiliation but missing funding (or vice versa)
    - ERROR: Missing both
    
    Args:
        has_affiliation: Whether publication has valid affiliation
        has_funding: Whether publication has funding acknowledgment
    
    Returns:
        ComplianceStatus enum value
    """
    if has_affiliation and has_funding:
        return ComplianceStatus.OK
    elif has_affiliation or has_funding:
        return ComplianceStatus.WARNING
    else:
        return ComplianceStatus.ERROR


# ===========================
# AUDIT EXECUTION
# ===========================

def audit_publication(publication: Publication, db: Session) -> Dict[str, any]:
    """
    Run compliance audit on a single publication and update database.
    
    Args:
        publication: Publication object to audit
        db: Database session
    
    Returns:
        Dictionary with audit results
    """
    # Validate affiliation
    has_affiliation, affiliation_matches = validate_affiliation(publication.contenido_texto)
    
    # Validate funding
    has_funding, funding_matches = validate_funding_acknowledgment(publication.contenido_texto)
    
    # Determine overall status
    compliance_status = determine_compliance_status(has_affiliation, has_funding)
    
    # Generate audit notes
    notes = []
    if has_affiliation:
        notes.append(f"✅ Affiliation found: {', '.join(affiliation_matches[:2])}")
    else:
        notes.append("❌ No valid affiliation found")
    
    if has_funding:
        notes.append(f"✅ Funding acknowledgment found: {', '.join(funding_matches[:2])}")
    else:
        notes.append("❌ No funding acknowledgment found")
    
    audit_notes_text = " | ".join(notes)
    
    # Update publication
    publication.has_valid_affiliation = has_affiliation
    publication.has_funding_ack = has_funding
    publication.anid_report_status = compliance_status
    publication.last_audit_date = datetime.utcnow()
    publication.audit_notes = audit_notes_text
    
    db.commit()
    
    return {
        "publication_id": publication.id,
        "titulo": publication.titulo[:80] + "..." if len(publication.titulo) > 80 else publication.titulo,
        "has_affiliation": has_affiliation,
        "affiliation_matches": affiliation_matches,
        "has_funding": has_funding,
        "funding_matches": funding_matches,
        "compliance_status": compliance_status.value,
        "audit_notes": audit_notes_text
    }


def run_full_audit(db: Session, publication_ids: List[int] = None) -> Dict[str, any]:
    """
    Run compliance audit on multiple publications.
    
    Args:
        db: Database session
        publication_ids: Optional list of specific publication IDs to audit.
                        If None, audits all publications with text content.
    
    Returns:
        Dictionary with summary statistics and detailed results
    """
    # Query publications
    query = db.query(Publication).filter(Publication.contenido_texto.isnot(None))
    
    if publication_ids:
        query = query.filter(Publication.id.in_(publication_ids))
    
    publications = query.all()
    
    # Run audit on each
    results = []
    stats = {
        "total_audited": 0,
        "status_ok": 0,
        "status_warning": 0,
        "status_error": 0,
        "has_affiliation": 0,
        "has_funding": 0
    }
    
    for pub in publications:
        result = audit_publication(pub, db)
        results.append(result)
        
        stats["total_audited"] += 1
        
        if result["compliance_status"] == ComplianceStatus.OK.value:
            stats["status_ok"] += 1
        elif result["compliance_status"] == ComplianceStatus.WARNING.value:
            stats["status_warning"] += 1
        else:
            stats["status_error"] += 1
        
        if result["has_affiliation"]:
            stats["has_affiliation"] += 1
        if result["has_funding"]:
            stats["has_funding"] += 1
    
    return {
        "summary": stats,
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }


# ===========================
# REPORTING
# ===========================

def get_compliance_report(db: Session) -> Dict[str, any]:
    """
    Generate a compliance report for all publications.
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with compliance statistics and breakdown
    """
    total_pubs = db.query(Publication).count()
    total_with_text = db.query(Publication).filter(Publication.contenido_texto.isnot(None)).count()
    
    # Status breakdown
    status_counts = {
        "ok": db.query(Publication).filter(Publication.anid_report_status == ComplianceStatus.OK).count(),
        "warning": db.query(Publication).filter(Publication.anid_report_status == ComplianceStatus.WARNING).count(),
        "error": db.query(Publication).filter(Publication.anid_report_status == ComplianceStatus.ERROR).count()
    }
    
    # Affiliation and funding stats
    affiliation_count = db.query(Publication).filter(Publication.has_valid_affiliation == True).count()
    funding_count = db.query(Publication).filter(Publication.has_funding_ack == True).count()
    
    # Publications needing attention (WARNING or ERROR status)
    non_compliant = db.query(Publication).filter(
        Publication.anid_report_status.in_([ComplianceStatus.WARNING, ComplianceStatus.ERROR])
    ).all()
    
    non_compliant_list = [
        {
            "id": pub.id,
            "titulo": pub.titulo[:80] + "..." if len(pub.titulo) > 80 else pub.titulo,
            "status": pub.anid_report_status.value,
            "audit_notes": pub.audit_notes,
            "has_affiliation": bool(pub.has_valid_affiliation),
            "has_funding": bool(pub.has_funding_ack)
        }
        for pub in non_compliant[:50]  # Limit to first 50
    ]
    
    return {
        "total_publications": total_pubs,
        "publications_with_text": total_with_text,
        "compliance_breakdown": status_counts,
        "affiliation_count": affiliation_count,
        "funding_count": funding_count,
        "compliance_rate": round((status_counts["ok"] / total_with_text * 100), 2) if total_with_text > 0 else 0,
        "non_compliant_publications": non_compliant_list,
        "generated_at": datetime.utcnow().isoformat()
    }


# ===========================
# INTEGRATION WITH SYNC
# ===========================

def audit_on_sync(publication: Publication, db: Session):
    """
    Hook to run audit automatically when a publication is synced/updated.
    This should be called from scraper.py after PDF text extraction.
    
    Args:
        publication: Newly synced/updated publication
        db: Database session
    """
    if publication.contenido_texto:
        audit_publication(publication, db)
        print(f"🤖 Robot audit completed for: {publication.titulo[:60]}...")


# ===========================
# COMMAND-LINE INTERFACE
# ===========================

if __name__ == "__main__":
    """
    Run compliance audit from command line.
    Usage: python -m backend.compliance
    """
    from core.models import get_session
    
    print("CECAN Compliance Robot - Starting Audit...")
    print("=" * 60)
    
    db = get_session()
    
    try:
        # Run full audit
        audit_results = run_full_audit(db)
        
        # Display summary
        print("\nAUDIT SUMMARY")
        print("-" * 60)
        summary = audit_results["summary"]
        print(f"Total publications audited: {summary['total_audited']}")
        print(f"  [OK] Compliant:        {summary['status_ok']}")
        print(f"  [WARNING]:             {summary['status_warning']}")
        print(f"  [ERROR]:               {summary['status_error']}")
        print(f"\nHas valid affiliation:     {summary['has_affiliation']}")
        print(f"Has funding acknowledgment: {summary['has_funding']}")
        
        # Compliance rate
        if summary['total_audited'] > 0:
            compliance_rate = (summary['status_ok'] / summary['total_audited']) * 100
            print(f"\nCompliance Rate: {compliance_rate:.1f}%")
        
        # Display some examples
        print("\nSAMPLE RESULTS (First 5):")
        print("-" * 60)
        for result in audit_results["results"][:5]:
            print(f"\n[{result['compliance_status']}] {result['titulo']}")
            print(f"   {result['audit_notes']}")
        
        # Generate full report
        print("\nGenerating compliance report...")
        report = get_compliance_report(db)
        print(f"[SUCCESS] Report generated at: {report['generated_at']}")
        print(f"          Compliance rate: {report['compliance_rate']}%")
        
    except Exception as e:
        print(f"[ERROR] Error during audit: {e}")
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("Audit completed!")
