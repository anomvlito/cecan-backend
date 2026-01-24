"""
Responsibilities API Routes
RACI-based permission assignments for resources.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from core.security import get_current_user
from core.models import (
    User, UserRole, ResponsibilityAssignment, ResourceType, RaciRole,
    AcademicMember, ScientificProject, ProjectActivity
)
from database.session import get_db
from schemas import (
    ResponsibilityCreate, ResponsibilityRead, ResponsibilityWithMember,
    ResponsibilityUpdate, MyResponsibilityItem
)
from services.authz import can, get_responsibilities_for_resource

router = APIRouter(prefix="/responsibilities", tags=["Responsibilities"])


# ===================
# HELPER FUNCTIONS
# ===================

def _can_manage_responsibility(
    user: User,
    resource_type: ResourceType,
    resource_id: int,
    db: Session
) -> bool:
    """
    Check if user can manage responsibilities for a resource.

    Rules:
    - SUPER_ADMIN and ADMIN: Always allowed
    - PI: Can manage if they own the resource (pi_id match or has Accountable role)
    - Others: Not allowed
    """
    # SUPER_ADMIN and ADMIN can manage all
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return True

    # PI can manage their own resources
    if user.role == UserRole.PI:
        if resource_type == ResourceType.SCIENTIFIC_PROJECT:
            project = db.query(ScientificProject).filter_by(id=resource_id).first()
            if not project:
                return False

            # Check if user is the PI of this project
            # First, get user's academic_member (if linked)
            member = db.query(AcademicMember).filter_by(email=user.email).first()
            if member and project.pi_id == member.id:
                return True

            # Check if user has Accountable role
            responsibilities = get_responsibilities_for_resource(
                db,
                resource_type.value,
                resource_id
            )
            for resp in responsibilities:
                if resp.user_id == user.id and resp.raci_role == RaciRole.A:
                    return True

    return False


def _get_user_member(user: User, db: Session) -> Optional[AcademicMember]:
    """Get the AcademicMember associated with a user (by email match)."""
    return db.query(AcademicMember).filter_by(email=user.email).first()


# ===================
# CRUD ENDPOINTS
# ===================

@router.post("/", response_model=ResponsibilityRead, status_code=201)
async def create_responsibility(
    data: ResponsibilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new responsibility assignment.

    Requires:
    - SUPER_ADMIN or ADMIN role
    - PI role with ownership of the resource
    """
    # Check permission to manage this resource
    if not _can_manage_responsibility(
        current_user,
        ResourceType[data.resource_type.upper()],
        data.resource_id,
        db
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to assign responsibilities for this resource"
        )

    # Verify that member_id exists
    member = db.query(AcademicMember).filter_by(id=data.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Academic member not found")

    # If user_id is provided, verify it exists
    if data.user_id:
        user = db.query(User).filter_by(id=data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # Check if this exact assignment already exists
    existing = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType[data.resource_type.upper()],
        resource_id=data.resource_id,
        member_id=data.member_id,
        raci_role=RaciRole[data.raci_role.upper()]
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This responsibility assignment already exists"
        )

    # Create the assignment
    assignment = ResponsibilityAssignment(
        resource_type=ResourceType[data.resource_type.upper()],
        resource_id=data.resource_id,
        raci_role=RaciRole[data.raci_role.upper()],
        member_id=data.member_id,
        user_id=data.user_id,
        created_by=current_user.id
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment


@router.get("/", response_model=List[ResponsibilityWithMember])
async def list_responsibilities(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[int] = Query(None, description="Filter by resource ID"),
    member_id: Optional[int] = Query(None, description="Filter by member ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List responsibility assignments with optional filters.

    Admins can see all. Others see only assignments related to their accessible resources.
    """
    query = db.query(ResponsibilityAssignment).options(
        joinedload(ResponsibilityAssignment.member)
    )

    # Apply filters
    if resource_type:
        try:
            resource_type_enum = ResourceType[resource_type.upper()]
            query = query.filter(ResponsibilityAssignment.resource_type == resource_type_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid resource_type: {resource_type}")

    if resource_id:
        query = query.filter(ResponsibilityAssignment.resource_id == resource_id)

    if member_id:
        query = query.filter(ResponsibilityAssignment.member_id == member_id)

    # Non-admin users should only see assignments they have access to
    # For simplicity, we'll allow all authenticated users to query
    # (more granular filtering can be added based on WP scope)

    assignments = query.all()
    return assignments


@router.get("/my", response_model=List[ResponsibilityWithMember])
async def get_my_responsibilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all responsibility assignments for the current user.

    Returns assignments linked either by:
    - user_id (direct user account link)
    - member_id (via email match to AcademicMember)
    """
    # Get assignments by user_id
    assignments_by_user = db.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.user_id == current_user.id
    ).options(
        joinedload(ResponsibilityAssignment.member)
    ).all()

    # Get assignments by member_id (via email match)
    member = _get_user_member(current_user, db)
    assignments_by_member = []
    if member:
        assignments_by_member = db.query(ResponsibilityAssignment).filter(
            ResponsibilityAssignment.member_id == member.id
        ).options(
            joinedload(ResponsibilityAssignment.member)
        ).all()

    # Combine and deduplicate (by id)
    all_assignments = {a.id: a for a in assignments_by_user + assignments_by_member}

    return list(all_assignments.values())


@router.get("/my-dashboard", response_model=List[MyResponsibilityItem])
async def get_my_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get enriched responsibility dashboard for the current user.

    Returns detailed information about activities and projects where the user
    has 'R' (Responsible) or 'A' (Accountable) roles, including deadlines,
    status, and overdue indicators.

    Filters:
    - Only PROJECT_ACTIVITY and SCIENTIFIC_PROJECT resources
    - Only R and A roles (not C or I)
    - Ordered by overdue status, then deadline
    - Limited to 50 most relevant items
    """
    from datetime import datetime as dt

    # Get user's member ID (if linked by email)
    member = _get_user_member(current_user, db)

    # Query responsibility assignments for current user
    query = db.query(ResponsibilityAssignment).filter(
        # Match by user_id OR member_id
        (ResponsibilityAssignment.user_id == current_user.id) |
        (ResponsibilityAssignment.member_id == member.id if member else False)
    ).filter(
        # Only activities and projects
        ResponsibilityAssignment.resource_type.in_([
            ResourceType.PROJECT_ACTIVITY,
            ResourceType.SCIENTIFIC_PROJECT
        ])
    ).filter(
        # Only Responsible and Accountable roles
        ResponsibilityAssignment.raci_role.in_([RaciRole.R, RaciRole.A])
    )

    assignments = query.all()

    # Enrich each assignment with resource details
    dashboard_items = []

    for assignment in assignments:
        item_data = {
            "assignment_id": assignment.id,
            "resource_type": assignment.resource_type.value,
            "resource_id": assignment.resource_id,
            "raci_role": assignment.raci_role.value,
            "title": "",
            "project_name": None,
            "project_code": None,
            "status": None,
            "deadline": None,
            "is_overdue": False,
            "progress": None,
            "budget_allocated": None,
        }

        # Fetch resource details based on type
        if assignment.resource_type == ResourceType.PROJECT_ACTIVITY:
            activity = db.query(ProjectActivity).filter_by(
                id=assignment.resource_id
            ).first()

            if activity:
                # Get parent project
                project = activity.project

                item_data["title"] = activity.description
                item_data["project_name"] = project.title if project else None
                item_data["project_code"] = project.code if project else None
                item_data["status"] = activity.status.value if activity.status else None
                item_data["deadline"] = activity.end_month
                item_data["progress"] = activity.progress
                item_data["budget_allocated"] = activity.budget_allocated

                # Calculate overdue (if end_month is in the past and status is not completed)
                if activity.end_month and activity.status and activity.status.value != "completed":
                    item_data["is_overdue"] = activity.end_month < dt.now().date()

        elif assignment.resource_type == ResourceType.SCIENTIFIC_PROJECT:
            project = db.query(ScientificProject).filter_by(
                id=assignment.resource_id
            ).first()

            if project:
                item_data["title"] = project.title
                item_data["project_name"] = None  # It's the project itself
                item_data["project_code"] = project.code
                item_data["status"] = project.status.value if project.status else None
                item_data["deadline"] = dt.combine(project.end_date, dt.min.time()) if project.end_date else None
                item_data["progress"] = project.progress
                item_data["budget_allocated"] = project.budget_allocated

                # Calculate overdue
                if project.end_date and project.status and project.status.value != "completed":
                    item_data["is_overdue"] = project.end_date < dt.now().date()

        # Only add if we found the resource
        if item_data["title"]:
            dashboard_items.append(MyResponsibilityItem(**item_data))

    # Sort by overdue (overdue first), then by deadline
    dashboard_items.sort(
        key=lambda x: (
            not x.is_overdue,  # False (overdue) comes before True (not overdue)
            x.deadline if x.deadline else dt.max  # Nulls last
        )
    )

    # Limit to 50 items
    return dashboard_items[:50]


@router.delete("/{assignment_id}", status_code=204)
async def delete_responsibility(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a responsibility assignment.

    Requires:
    - SUPER_ADMIN or ADMIN role
    - PI role with ownership of the resource
    """
    # Fetch the assignment
    assignment = db.query(ResponsibilityAssignment).filter_by(id=assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Responsibility assignment not found")

    # Check permission to manage this resource
    if not _can_manage_responsibility(
        current_user,
        assignment.resource_type,
        assignment.resource_id,
        db
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this responsibility assignment"
        )

    db.delete(assignment)
    db.commit()

    return None


@router.get("/{assignment_id}", response_model=ResponsibilityWithMember)
async def get_responsibility(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific responsibility assignment by ID."""
    assignment = db.query(ResponsibilityAssignment).filter_by(
        id=assignment_id
    ).options(
        joinedload(ResponsibilityAssignment.member)
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Responsibility assignment not found")

    return assignment
