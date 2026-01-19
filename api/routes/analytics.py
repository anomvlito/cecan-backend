"""
Analytics Routes for CECAN Platform
API endpoints for collaboration matrix and research analytics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel

from core.security import get_current_user
from core.models import User, Publication, AcademicMember, ResearcherPublication, ResearcherDetails, Project, ProjectResearcher
from database.session import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ===========================
# TOGGLE RELATION SCHEMA
# ===========================

class ToggleRelationRequest(BaseModel):
    project_id: int
    researcher_id: int


class ToggleRelationResponse(BaseModel):
    status: str  # "created" | "deleted"
    success: bool


class ProjectInfo(BaseModel):
    id: int
    title: str
    wp_name: Optional[str] = None
    researcher_ids: List[int]

    class Config:
        from_attributes = True


class ProjectMatrixResponse(BaseModel):
    researchers: List["ResearcherInfo"]
    projects: List[ProjectInfo]


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


@router.get("/project-matrix", response_model=ProjectMatrixResponse)
async def get_project_matrix(
    include_all: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns project-researcher matrix data for the Data Studio editor.

    Args:
        include_all: If False (default), only return researchers with at least one project connection.
                     If True, return all active researchers.

    Returns:
        - researchers: List of researchers with id, name, and orcid
        - projects: List of projects with id, title, wp_name, and researcher_ids
    """
    try:
        # DEBUG: Count total connections in database
        total_connections = db.query(ProjectResearcher).count()
        print(f"[DEBUG project-matrix] Total ProjectResearcher rows in DB: {total_connections}")

        # Get all projects with researcher connections first
        projects_query = (
            db.query(Project)
            .options(
                joinedload(Project.researcher_connections),
                joinedload(Project.wp)
            )
            .order_by(Project.title)
            .all()
        )

        # DEBUG: Log connections per project
        for p in projects_query[:5]:  # First 5 projects
            print(f"[DEBUG] Project '{p.title[:30]}' has {len(p.researcher_connections)} connections")

        projects = [
            ProjectInfo(
                id=p.id,
                title=p.title,
                wp_name=p.wp.name if p.wp else None,
                researcher_ids=[conn.member_id for conn in p.researcher_connections]
            )
            for p in projects_query
        ]

        # DEBUG: Total projects with connections
        projects_with_conns = sum(1 for p in projects if p.researcher_ids)
        print(f"[DEBUG project-matrix] Projects with connections: {projects_with_conns}/{len(projects)}")

        if include_all:
            # Get ALL active researchers
            researchers_query = (
                db.query(AcademicMember)
                .filter(AcademicMember.member_type == 'researcher')
                .filter(AcademicMember.is_active == True)
                .options(joinedload(AcademicMember.researcher_details))
                .order_by(AcademicMember.full_name)
                .all()
            )
        else:
            # OPTIMIZED: Only get researchers with at least one project connection
            connected_member_ids = (
                db.query(ProjectResearcher.member_id)
                .distinct()
                .subquery()
            )

            researchers_query = (
                db.query(AcademicMember)
                .filter(AcademicMember.member_type == 'researcher')
                .filter(AcademicMember.is_active == True)
                .filter(AcademicMember.id.in_(connected_member_ids))
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

        return ProjectMatrixResponse(
            researchers=researchers,
            projects=projects
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating project matrix: {str(e)}"
        )


@router.post("/toggle-relation", response_model=ToggleRelationResponse)
async def toggle_relation(
    request: ToggleRelationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle a project-researcher relationship.

    - If the relationship EXISTS -> DELETE it
    - If the relationship DOES NOT EXIST -> CREATE it

    Returns the action taken (created/deleted) and success status.
    """
    try:
        # Verify project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

        # Verify researcher exists
        researcher = db.query(AcademicMember).filter(
            AcademicMember.id == request.researcher_id,
            AcademicMember.member_type == 'researcher'
        ).first()
        if not researcher:
            raise HTTPException(status_code=404, detail=f"Researcher {request.researcher_id} not found")

        # Check if relationship exists
        existing_relation = db.query(ProjectResearcher).filter(
            ProjectResearcher.project_id == request.project_id,
            ProjectResearcher.member_id == request.researcher_id
        ).first()

        if existing_relation:
            # DELETE the relationship
            db.delete(existing_relation)
            db.commit()
            return ToggleRelationResponse(status="deleted", success=True)
        else:
            # CREATE the relationship
            new_relation = ProjectResearcher(
                project_id=request.project_id,
                member_id=request.researcher_id
            )
            db.add(new_relation)
            db.commit()
            return ToggleRelationResponse(status="created", success=True)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error toggling relation: {str(e)}"
        )
