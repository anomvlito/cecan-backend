"""
Analytics Routes for CECAN Platform
API endpoints for collaboration matrix and research analytics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel

from core.security import get_current_user
from core.models import User, Publication, AcademicMember, ResearcherPublication, ResearcherDetails
from database.session import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ===========================
# SCHEMAS
# ===========================

class ResearcherInfo(BaseModel):
    id: int
    name: str
    orcid: Optional[str] = None

    class Config:
        from_attributes = True


class PublicationInfo(BaseModel):
    id: int
    title: str
    year: Optional[str] = None
    author_ids: List[int]

    class Config:
        from_attributes = True


class CollaborationMatrixResponse(BaseModel):
    researchers: List[ResearcherInfo]
    publications: List[PublicationInfo]


# ===========================
# ENDPOINTS
# ===========================

@router.get("/collaboration-matrix", response_model=CollaborationMatrixResponse)
async def get_collaboration_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns collaboration matrix data optimized for frontend rendering.

    Returns:
        - researchers: List of researchers with id, name, and orcid
        - publications: List of publications with id, title, year, and author_ids

    The frontend can use author_ids to determine which cells to mark in the matrix.
    """
    try:
        # Get all researchers (member_type='researcher') with their details
        researchers_query = (
            db.query(AcademicMember)
            .filter(AcademicMember.member_type == 'researcher')
            .filter(AcademicMember.is_active == True)
            .options(joinedload(AcademicMember.researcher_details))
            .order_by(AcademicMember.full_name)
            .all()
        )

        researchers = [
            ResearcherInfo(
                id=r.id,
                name=r.full_name,
                orcid=r.researcher_details.orcid if r.researcher_details else None
            )
            for r in researchers_query
        ]

        # Get all publications with their researcher connections (eager loading to avoid N+1)
        publications_query = (
            db.query(Publication)
            .options(joinedload(Publication.researcher_connections))
            .order_by(Publication.year.desc(), Publication.title)
            .all()
        )

        publications = [
            PublicationInfo(
                id=p.id,
                title=p.title,
                year=p.year,
                author_ids=[conn.member_id for conn in p.researcher_connections]
            )
            for p in publications_query
        ]

        return CollaborationMatrixResponse(
            researchers=researchers,
            publications=publications
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating collaboration matrix: {str(e)}"
        )


@router.get("/collaboration-stats")
async def get_collaboration_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns summary statistics about collaborations.
    """
    try:
        # Count total researchers
        total_researchers = (
            db.query(AcademicMember)
            .filter(AcademicMember.member_type == 'researcher')
            .filter(AcademicMember.is_active == True)
            .count()
        )

        # Count total publications
        total_publications = db.query(Publication).count()

        # Count total connections (researcher-publication pairs)
        total_connections = db.query(ResearcherPublication).count()

        # Average collaborators per publication
        avg_collaborators = (
            total_connections / total_publications if total_publications > 0 else 0
        )

        return {
            "total_researchers": total_researchers,
            "total_publications": total_publications,
            "total_connections": total_connections,
            "avg_collaborators_per_publication": round(avg_collaborators, 2)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating collaboration stats: {str(e)}"
        )
