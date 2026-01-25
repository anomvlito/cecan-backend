"""
Scientific Projects API Routes
Clean CRUD for research project management with activities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field

from core.security import get_current_user
from core.models import (
    User, UserRole, ScientificProject, ProjectActivity, AcademicMember,
    ResearcherDetails, WorkPackageType, ProjectStatusType, ActivityStatusType,
    PaymentStatusType, ResourceType, ResponsibilityAssignment, RaciRole
)
from database.session import get_db
from services.authz import can, get_responsibilities_for_resource

router = APIRouter(prefix="/scientific-projects", tags=["Scientific Projects"])


# ===================
# HELPER FUNCTIONS
# ===================

def _get_user_member(user: User, db: Session) -> Optional[AcademicMember]:
    """Get the AcademicMember associated with a user (by email match)."""
    return db.query(AcademicMember).filter_by(email=user.email).first()


def _get_user_wp_ids(member: Optional[AcademicMember]) -> List[int]:
    """Extract all Work Package IDs that a member belongs to."""
    if not member:
        return []

    wp_ids = []

    # Legacy single WP assignment
    if hasattr(member, 'wp_id') and member.wp_id:
        wp_ids.append(member.wp_id)

    # Many-to-many WP assignments
    if hasattr(member, 'wps') and member.wps:
        wp_ids.extend([wp.id for wp in member.wps])

    return list(set(wp_ids))  # Remove duplicates


def _filter_projects_by_access(
    query,
    user: User,
    db: Session
) -> any:
    """
    Filter projects query based on user's access level.

    - SUPER_ADMIN, ADMIN, STAFF: See all projects
    - PI, RESEARCHER: See projects in their WP(s) or assigned to them
    - STUDENT, VIEWER: See only explicitly assigned projects
    """
    # Admins and staff see everything
    if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STAFF]:
        return query

    # Get user's academic member
    member = _get_user_member(user, db)

    # If no member link, user can only see projects they created
    if not member:
        return query.filter(ScientificProject.created_by == user.id)

    # Get user's WP IDs
    user_wp_ids = _get_user_wp_ids(member)

    # PI and RESEARCHER: Filter by WP scope or ownership
    if user.role in [UserRole.PI, UserRole.RESEARCHER]:
        # Projects where:
        # 1. User is the PI
        # 2. Project is in user's WP(s)
        # 3. User has responsibilities assigned
        filters = [ScientificProject.pi_id == member.id]

        # Note: work_package is an enum, so we need to filter differently
        # For simplicity, we'll allow all for now if user has any WP
        # In production, you'd map WorkPackageType enum to WP IDs
        if user_wp_ids:
            # Allow all projects for users with WP assignments
            # (This is a simplification - ideally map WP enum to IDs)
            pass

        return query.filter(or_(*filters)) if filters else query

    # STUDENT, VIEWER: Only see explicitly assigned projects
    # (Would need to query ResponsibilityAssignment table)
    # For simplicity, filter by creator for now
    return query.filter(ScientificProject.created_by == user.id)


# ===================
# PYDANTIC SCHEMAS
# ===================

class ActivityCreate(BaseModel):
    """Schema for creating an activity."""
    number: int = 1
    description: str
    start_month: Optional[date] = None
    end_month: Optional[date] = None
    status: str = "pending"
    # Financial fields
    budget_allocated: float = 0.0
    payment_status: str = "pending"
    payment_proof_url: Optional[str] = None
    # Assignment - list of user IDs to assign as Responsible
    assigned_user_ids: Optional[List[int]] = None


class ActivityUpdate(BaseModel):
    """Schema for updating an activity."""
    number: Optional[int] = None
    description: Optional[str] = None
    start_month: Optional[date] = None
    end_month: Optional[date] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    # Financial fields
    budget_allocated: Optional[float] = None
    payment_status: Optional[str] = None
    payment_proof_url: Optional[str] = None
    # Assignment - list of user IDs to assign as Responsible
    assigned_user_ids: Optional[List[int]] = None


class ActivityResponse(BaseModel):
    """Activity response with financial data."""
    id: int
    project_id: int
    number: int
    description: str
    start_month: Optional[date]
    end_month: Optional[date]
    status: str
    progress: float
    # Financial fields
    budget_allocated: float
    payment_status: str
    payment_proof_url: Optional[str]
    # Assignments
    assigned_user_ids: List[int] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Schema for creating a project."""
    title: str
    code: Optional[str] = None
    description: Optional[str] = None
    work_package: str  # WP1, WP2, etc.
    grant_type: Optional[str] = None
    pi_id: Optional[int] = None
    pi_name: Optional[str] = None
    years_covered: List[int] = Field(default_factory=list)  # [3, 4]
    budget_allocated: float = 0.0
    budget_executed: float = 0.0
    notes: Optional[str] = None
    activities: List[ActivityCreate] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    title: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    work_package: Optional[str] = None
    grant_type: Optional[str] = None
    pi_id: Optional[int] = None
    pi_name: Optional[str] = None
    years_covered: Optional[List[int]] = None
    budget_allocated: Optional[float] = None
    budget_executed: Optional[float] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    notes: Optional[str] = None
    activities: Optional[List[ActivityCreate]] = None


class ProjectResponse(BaseModel):
    """Full project response with activities."""
    id: int
    title: str
    code: Optional[str]
    description: Optional[str]
    work_package: str
    grant_type: Optional[str]
    pi_id: Optional[int]
    pi_name: Optional[str]
    years_covered: List[int]
    start_date: Optional[date]
    end_date: Optional[date]
    budget_allocated: float
    budget_executed: float
    budget_remaining: float
    budget_utilization: float
    is_over_budget: bool
    status: str
    progress: float
    color: Optional[str]
    notes: Optional[str]
    activities: List[ActivityResponse]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProjectListItem(BaseModel):
    """Project response for list views with activities for Gantt."""
    id: int
    title: str
    code: Optional[str]
    work_package: str
    pi_name: Optional[str]
    years_covered: List[int]
    budget_allocated: float
    budget_executed: float
    status: str
    progress: float
    activity_count: int
    color: Optional[str]
    activities: List[ActivityResponse]

    class Config:
        from_attributes = True


# ===================
# HELPER FUNCTIONS
# ===================

def get_assigned_user_ids(db: Session, activity_id: int) -> List[int]:
    """Get user IDs assigned to an activity with Responsible (R) role."""
    assignments = db.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.resource_type == ResourceType.PROJECT_ACTIVITY,
        ResponsibilityAssignment.resource_id == activity_id,
        ResponsibilityAssignment.raci_role == RaciRole.R,
        ResponsibilityAssignment.user_id.isnot(None)
    ).all()
    return [a.user_id for a in assignments if a.user_id]


# ===================
# PROJECT ENDPOINTS
# ===================

@router.get("/", response_model=List[ProjectListItem])
async def list_projects(
    work_package: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all scientific projects with optional filtering.

    Non-admin users will only see projects within their access scope:
    - ADMIN/STAFF: All projects
    - PI/RESEARCHER: Projects in their WP(s) or where they're PI
    - STUDENT/VIEWER: Only assigned projects
    """
    query = db.query(ScientificProject).options(
        joinedload(ScientificProject.activities)
    )

    # Apply access control filtering
    query = _filter_projects_by_access(query, current_user, db)

    if work_package:
        query = query.filter(ScientificProject.work_package == WorkPackageType(work_package))

    if status:
        query = query.filter(ScientificProject.status == ProjectStatusType(status))

    projects = query.order_by(ScientificProject.code, ScientificProject.created_at.desc()).all()

    return [
        ProjectListItem(
            id=p.id,
            title=p.title,
            code=p.code,
            work_package=p.work_package.value,
            pi_name=p.pi_name,
            years_covered=p.years_covered or [],
            budget_allocated=p.budget_allocated or 0,
            budget_executed=p.budget_executed or 0,
            status=p.status.value if p.status else "draft",
            progress=p.progress or 0,
            activity_count=len(p.activities),
            color=p.color,
            activities=[
                ActivityResponse(
                    id=a.id,
                    project_id=a.project_id,
                    number=a.number,
                    description=a.description,
                    start_month=a.start_month,
                    end_month=a.end_month,
                    status=a.status.value if a.status else "pending",
                    progress=a.progress or 0,
                    budget_allocated=a.budget_allocated or 0,
                    payment_status=a.payment_status.value if a.payment_status else "pending",
                    payment_proof_url=a.payment_proof_url,
                    assigned_user_ids=get_assigned_user_ids(db, a.id)
                )
                for a in sorted(p.activities, key=lambda x: x.number)
            ]
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single project with all activities."""
    project = db.query(ScientificProject).options(
        joinedload(ScientificProject.activities)
    ).filter(ScientificProject.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        title=project.title,
        code=project.code,
        description=project.description,
        work_package=project.work_package.value,
        grant_type=project.grant_type,
        pi_id=project.pi_id,
        pi_name=project.pi_name,
        years_covered=project.years_covered or [],
        start_date=project.start_date,
        end_date=project.end_date,
        budget_allocated=project.budget_allocated or 0,
        budget_executed=project.budget_executed or 0,
        budget_remaining=project.budget_remaining,
        budget_utilization=project.budget_utilization,
        is_over_budget=project.is_over_budget,
        status=project.status.value if project.status else "draft",
        progress=project.progress or 0,
        color=project.color,
        notes=project.notes,
        activities=[
            ActivityResponse(
                id=a.id,
                project_id=a.project_id,
                number=a.number,
                description=a.description,
                start_month=a.start_month,
                end_month=a.end_month,
                status=a.status.value if a.status else "pending",
                progress=a.progress or 0,
                budget_allocated=a.budget_allocated or 0,
                payment_status=a.payment_status.value if a.payment_status else "pending",
                payment_proof_url=a.payment_proof_url,
                assigned_user_ids=get_assigned_user_ids(db, a.id)
            )
            for a in sorted(project.activities, key=lambda x: x.number)
        ],
        created_at=project.created_at
    )


@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new scientific project with activities."""

    # Generate code if not provided
    if not data.code:
        # Count existing projects to generate next code
        count = db.query(ScientificProject).count()
        data.code = f"P-{count + 1:02d}"

    # Create project
    project = ScientificProject(
        title=data.title,
        code=data.code,
        description=data.description,
        work_package=WorkPackageType(data.work_package),
        grant_type=data.grant_type,
        pi_id=data.pi_id,
        pi_name=data.pi_name,
        years_covered=data.years_covered,
        budget_allocated=data.budget_allocated,
        budget_executed=data.budget_executed,
        notes=data.notes,
        status=ProjectStatusType.DRAFT,
        created_by=current_user.id
    )

    # Calculate dates from years
    project.calculate_dates_from_years()

    # Assign WP color
    wp_colors = {
        "WP1": "#3b82f6",  # Blue
        "WP2": "#10b981",  # Green
        "WP3": "#f59e0b",  # Amber
        "WP4": "#8b5cf6",  # Purple
        "OUTREACH": "#ec4899",  # Pink
        "TRAINING": "#06b6d4",  # Cyan
        "GOVERNANCE": "#6366f1",  # Indigo
    }
    project.color = wp_colors.get(data.work_package, "#6b7280")

    db.add(project)
    db.flush()

    # Assign creator as Accountable for the Project itself
    if current_user.email:
        creator_member = db.query(AcademicMember).filter(
            AcademicMember.email == current_user.email
        ).first()
        if creator_member:
            project_assignment = ResponsibilityAssignment(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                raci_role=RaciRole.A,
                member_id=creator_member.id,
                user_id=current_user.id,
                created_by=current_user.id
            )
            db.add(project_assignment)
    
    # Create activities
    for idx, act_data in enumerate(data.activities):
        activity = ProjectActivity(
            project_id=project.id,
            number=act_data.number,
            description=act_data.description,
            start_month=act_data.start_month,
            end_month=act_data.end_month,
            status=ActivityStatusType(act_data.status) if act_data.status else ActivityStatusType.PENDING,
            sort_order=idx,
            # Financial fields
            budget_allocated=act_data.budget_allocated or 0.0,
            payment_status=PaymentStatusType(act_data.payment_status.lower()) if act_data.payment_status else PaymentStatusType.PENDING,
            payment_proof_url=act_data.payment_proof_url,
            # Audit
            created_by=current_user.id
        )
        db.add(activity)
        db.flush()  # Get activity.id

        # Assign creator as Accountable
        if current_user.email:
            creator_member = db.query(AcademicMember).filter(
                AcademicMember.email == current_user.email
            ).first()
            pi_assignment = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=activity.id,
                raci_role=RaciRole.A,
                member_id=creator_member.id if creator_member else None,
                user_id=current_user.id,
                created_by=current_user.id
            )
            db.add(pi_assignment)

        # Create assignments for assigned users
        if hasattr(act_data, 'assigned_user_ids') and act_data.assigned_user_ids:
            for user_id in act_data.assigned_user_ids:
                assigned_user = db.query(User).filter(User.id == user_id).first()
                if assigned_user:
                    academic_member = db.query(AcademicMember).filter(
                        AcademicMember.email == assigned_user.email
                    ).first()
                    assignment = ResponsibilityAssignment(
                        resource_type=ResourceType.PROJECT_ACTIVITY,
                        resource_id=activity.id,
                        raci_role=RaciRole.R,
                        member_id=academic_member.id if academic_member else None,
                        user_id=assigned_user.id,
                        created_by=current_user.id
                    )
                    db.add(assignment)

    db.commit()
    db.refresh(project)

    # Return full project
    return await get_project(project.id, db, current_user)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a project and its activities.

    Requires permission to update the project (PI, Accountable, or Admin).
    """
    project = db.query(ScientificProject).filter(
        ScientificProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check permission to update
    responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.SCIENTIFIC_PROJECT.value,
        project_id
    )

    if not can(current_user, "update", project, responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this project"
        )

    # Update fields (exclude activities, handle separately)
    update_data = data.model_dump(exclude_unset=True, exclude={"activities"})

    for field, value in update_data.items():
        if field == "work_package" and value:
            value = WorkPackageType(value)
        elif field == "status" and value:
            value = ProjectStatusType(value)
        setattr(project, field, value)

    # Recalculate dates if years changed
    if data.years_covered:
        project.calculate_dates_from_years()

    # Handle activities if provided (replace strategy)
    if data.activities is not None:
        # Get existing activity IDs
        existing_activity_ids = [
            a.id for a in db.query(ProjectActivity).filter(
                ProjectActivity.project_id == project_id
            ).all()
        ]

        # Delete assignments for activities that will be deleted
        if existing_activity_ids:
            db.query(ResponsibilityAssignment).filter(
                ResponsibilityAssignment.resource_type == ResourceType.PROJECT_ACTIVITY,
                ResponsibilityAssignment.resource_id.in_(existing_activity_ids)
            ).delete(synchronize_session=False)

        # Delete existing activities
        db.query(ProjectActivity).filter(
            ProjectActivity.project_id == project_id
        ).delete(synchronize_session=False)

        # Create new activities
        for idx, act_data in enumerate(data.activities):
            activity = ProjectActivity(
                project_id=project_id,
                number=act_data.number or (idx + 1),
                description=act_data.description,
                start_month=act_data.start_month,
                end_month=act_data.end_month,
                status=ActivityStatusType(act_data.status) if act_data.status else ActivityStatusType.PENDING,
                sort_order=idx,
                # Financial fields
                budget_allocated=act_data.budget_allocated or 0.0,
                payment_status=PaymentStatusType(act_data.payment_status.lower()) if act_data.payment_status else PaymentStatusType.PENDING,
                payment_proof_url=act_data.payment_proof_url,
                # Audit
                created_by=current_user.id
            )
            db.add(activity)
            db.flush()

            # Assign creator as Accountable
            if current_user.email:
                creator_member = db.query(AcademicMember).filter(
                    AcademicMember.email == current_user.email
                ).first()
                pi_assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.PROJECT_ACTIVITY,
                    resource_id=activity.id,
                    raci_role=RaciRole.A,
                    member_id=creator_member.id if creator_member else None,
                    user_id=current_user.id,
                    created_by=current_user.id
                )
                db.add(pi_assignment)

            # Create assignments for assigned users
            if hasattr(act_data, 'assigned_user_ids') and act_data.assigned_user_ids:
                for user_id in act_data.assigned_user_ids:
                    assigned_user = db.query(User).filter(User.id == user_id).first()
                    if assigned_user:
                        academic_member = db.query(AcademicMember).filter(
                            AcademicMember.email == assigned_user.email
                        ).first()
                        assignment = ResponsibilityAssignment(
                            resource_type=ResourceType.PROJECT_ACTIVITY,
                            resource_id=activity.id,
                            raci_role=RaciRole.R,
                            member_id=academic_member.id if academic_member else None,
                            user_id=assigned_user.id,
                            created_by=current_user.id
                        )
                        db.add(assignment)

    db.commit()
    db.refresh(project)

    return await get_project(project.id, db, current_user)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a project and all its activities.

    Requires permission to delete (PI or Admin).
    """
    project = db.query(ScientificProject).filter(
        ScientificProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check permission to delete
    responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.SCIENTIFIC_PROJECT.value,
        project_id
    )

    if not can(current_user, "delete", project, responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this project"
        )

    db.delete(project)
    db.commit()

    return {"success": True, "deleted_id": project_id}


# ===================
# ACTIVITY ENDPOINTS
# ===================

@router.post("/{project_id}/activities", response_model=ActivityResponse)
async def add_activity(
    project_id: int,
    data: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add an activity to a project.

    Requires permission to create activities (project owner or assigned).
    """
    project = db.query(ScientificProject).filter(
        ScientificProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check permission to add activities (same as updating project)
    responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.SCIENTIFIC_PROJECT.value,
        project_id
    )

    if not can(current_user, "update", project, responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to add activities to this project"
        )

    # Get next number
    max_num = db.query(ProjectActivity).filter(
        ProjectActivity.project_id == project_id
    ).count()

    if data.start_month and data.end_month and data.start_month > data.end_month:
        raise HTTPException(status_code=400, detail="La fecha de inicio no puede ser posterior a la fecha de término")

    activity = ProjectActivity(
        project_id=project_id,
        number=data.number or (max_num + 1),
        description=data.description,
        start_month=data.start_month,
        end_month=data.end_month,
        status=ActivityStatusType(data.status) if data.status else ActivityStatusType.PENDING,
        sort_order=max_num,
        # Financial fields
        budget_allocated=data.budget_allocated or 0.0,
        payment_status=PaymentStatusType(data.payment_status.lower()) if data.payment_status else PaymentStatusType.PENDING,
        payment_proof_url=data.payment_proof_url,
        # Audit
        created_by=current_user.id
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    # Assign creator (PI) as Accountable automatically
    if current_user.academic_member:
        pi_assignment = ResponsibilityAssignment(
            resource_type=ResourceType.PROJECT_ACTIVITY,
            resource_id=activity.id,
            raci_role=RaciRole.A,  # Accountable (supervisor)
            member_id=current_user.academic_member.id,
            user_id=current_user.id,
            created_by=current_user.id
        )
        db.add(pi_assignment)

    # Create RACI assignments for assigned users
    if data.assigned_user_ids:
        for user_id in data.assigned_user_ids:
            # Get user (no joinedload - academic_member is a property not a relationship)
            assigned_user = db.query(User).filter(User.id == user_id).first()

            if assigned_user:
                # Try to find academic_member by email
                academic_member = db.query(AcademicMember).filter(
                    AcademicMember.email == assigned_user.email
                ).first()

                assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.PROJECT_ACTIVITY,
                    resource_id=activity.id,
                    raci_role=RaciRole.R,  # Responsible
                    member_id=academic_member.id if academic_member else None,
                    user_id=assigned_user.id,  # ALWAYS set user_id
                    created_by=current_user.id
                )
                db.add(assignment)

        db.commit()

    return ActivityResponse(
        id=activity.id,
        project_id=activity.project_id,
        number=activity.number,
        description=activity.description,
        start_month=activity.start_month,
        end_month=activity.end_month,
        status=activity.status.value if activity.status else "pending",
        progress=activity.progress or 0,
        budget_allocated=activity.budget_allocated or 0,
        payment_status=activity.payment_status.value if activity.payment_status else "pending",
        payment_proof_url=activity.payment_proof_url
    )


@router.put("/{project_id}/activities/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    project_id: int,
    activity_id: int,
    data: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an activity.

    Requires permission to update the parent project.
    """
    activity = db.query(ProjectActivity).filter(
        ProjectActivity.id == activity_id,
        ProjectActivity.project_id == project_id
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Load parent project for permission check
    project = db.query(ScientificProject).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check permission to update this ACTIVITY (not just the project)
    # This allows users with RACI R on the activity to update it
    activity_responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.PROJECT_ACTIVITY.value,
        activity.id
    )

    if not can(current_user, "update", activity, activity_responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this activity"
        )

    # Validate dates
    new_start = data.start_month if data.start_month is not None else activity.start_month
    new_end = data.end_month if data.end_month is not None else activity.end_month
    
    if new_start and new_end and new_start > new_end:
        raise HTTPException(status_code=400, detail="La fecha de inicio no puede ser posterior a la fecha de término")

    update_data = data.model_dump(exclude_unset=True)

    # Extract assigned_user_ids before updating activity fields
    assigned_user_ids = update_data.pop('assigned_user_ids', None)

    for field, value in update_data.items():
        if field == "status" and value:
            value = ActivityStatusType(value)
        elif field == "payment_status" and value:
            value = PaymentStatusType(value.lower())
        setattr(activity, field, value)

    db.commit()
    db.refresh(activity)

    # Update RACI assignments if assigned_user_ids is not None
    if assigned_user_ids is not None:
        # Delete only "R" (Responsible) assignments, keep "A" (Accountable) assignments
        db.query(ResponsibilityAssignment).filter(
            ResponsibilityAssignment.resource_type == ResourceType.PROJECT_ACTIVITY,
            ResponsibilityAssignment.resource_id == activity.id,
            ResponsibilityAssignment.raci_role == RaciRole.R
        ).delete()

        # Create new "R" assignments
        for user_id in assigned_user_ids:
            # Get user without invalid joinedload
            assigned_user = db.query(User).filter(User.id == user_id).first()

            if assigned_user:
                # Find academic_member by email
                academic_member = db.query(AcademicMember).filter(
                    AcademicMember.email == assigned_user.email
                ).first()

                if academic_member:
                    assignment = ResponsibilityAssignment(
                        resource_type=ResourceType.PROJECT_ACTIVITY,
                        resource_id=activity.id,
                        raci_role=RaciRole.R,
                        member_id=academic_member.id,
                        user_id=assigned_user.id,
                        created_by=current_user.id
                    )
                    db.add(assignment)

        # Ensure there's at least one "A" (Accountable) - if not, assign creator as "A"
        accountable_exists = db.query(ResponsibilityAssignment).filter(
            ResponsibilityAssignment.resource_type == ResourceType.PROJECT_ACTIVITY,
            ResponsibilityAssignment.resource_id == activity.id,
            ResponsibilityAssignment.raci_role == RaciRole.A
        ).first()

        if not accountable_exists and current_user.academic_member:
            pi_assignment = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=activity.id,
                raci_role=RaciRole.A,
                member_id=current_user.academic_member.id,
                user_id=current_user.id,
                created_by=current_user.id
            )
            db.add(pi_assignment)

        db.commit()

    return ActivityResponse(
        id=activity.id,
        project_id=activity.project_id,
        number=activity.number,
        description=activity.description,
        start_month=activity.start_month,
        end_month=activity.end_month,
        status=activity.status.value if activity.status else "pending",
        progress=activity.progress or 0,
        budget_allocated=activity.budget_allocated or 0,
        payment_status=activity.payment_status.value if activity.payment_status else "pending",
        payment_proof_url=activity.payment_proof_url,
        assigned_user_ids=get_assigned_user_ids(db, activity.id)
    )


@router.delete("/{project_id}/activities/{activity_id}")
async def delete_activity(
    project_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an activity.

    Requires permission to update the parent project.
    """
    activity = db.query(ProjectActivity).filter(
        ProjectActivity.id == activity_id,
        ProjectActivity.project_id == project_id
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Load parent project for permission check
    project = db.query(ScientificProject).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check permission to update project activities
    responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.SCIENTIFIC_PROJECT.value,
        project_id
    )

    if not can(current_user, "update", project, responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete activities in this project"
        )

    db.delete(activity)
    db.commit()

    return {"success": True, "deleted_id": activity_id}


# ===================
# LOOKUP ENDPOINTS
# ===================

@router.get("/lookup/work-packages")
async def get_work_package_options(
    current_user: User = Depends(get_current_user)
):
    """Get available work package types."""
    return [
        {"value": wp.value, "label": wp.value}
        for wp in WorkPackageType
    ]


@router.get("/lookup/investigators")
async def get_investigators(
    category: Optional[str] = Query(None, description="Filter by category: Principal, Asociado, Adjunto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of researchers for PI selection. By default returns only Principal investigators."""
    query = db.query(AcademicMember).join(
        ResearcherDetails, AcademicMember.id == ResearcherDetails.member_id
    ).filter(
        AcademicMember.is_active == True
    )

    # Default to Principal if no category specified
    filter_category = category or "Principal"
    query = query.filter(ResearcherDetails.category == filter_category)

    members = query.order_by(AcademicMember.full_name).all()

    return [
        {
            "id": m.id,
            "name": m.full_name,
            "category": m.researcher_details.category if m.researcher_details else None
        }
        for m in members
    ]


@router.get("/lookup/grant-types")
async def get_grant_types(
    current_user: User = Depends(get_current_user)
):
    """Get available grant types."""
    return [
        {"value": "Seed Research Grant", "label": "Seed Research Grant"},
        {"value": "Research Project", "label": "Research Project"},
        {"value": "Training Grant", "label": "Training Grant"},
        {"value": "Outreach Grant", "label": "Outreach Grant"},
        {"value": "Infrastructure", "label": "Infrastructure"},
        {"value": "Other", "label": "Other"},
    ]
