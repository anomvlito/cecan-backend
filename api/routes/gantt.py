"""
Gantt Chart API Routes
Full CRUD for Gantt tasks with DHTMLX-compatible format.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import tempfile
import os

from core.security import get_current_user
from core.models import (
    User, GanttTask, GanttTaskStatus, GanttLink,
    GanttAlert, GanttAlertType, GanttImportLog, WorkPackage
)
from database.session import get_db
from services.gantt_import_service import GanttImportService

router = APIRouter(prefix="/gantt", tags=["Gantt"])


# ===================
# PYDANTIC SCHEMAS
# ===================

class GanttTaskBase(BaseModel):
    """Base schema for Gantt task."""
    text: str
    start_date: datetime
    end_date: datetime
    duration: Optional[int] = None
    progress: float = 0.0
    parent_id: Optional[int] = None
    task_type: str = "task"
    priority: int = 2
    owner_id: Optional[int] = None
    notes: Optional[str] = None
    color: Optional[str] = None
    budget_allocated: float = 0.0
    budget_executed: float = 0.0


class GanttTaskCreate(GanttTaskBase):
    """Schema for creating a task."""
    wp_id: Optional[int] = None


class GanttTaskUpdate(BaseModel):
    """Schema for updating a task (partial)."""
    text: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration: Optional[int] = None
    progress: Optional[float] = None
    parent_id: Optional[int] = None
    status: Optional[str] = None
    owner_id: Optional[int] = None
    notes: Optional[str] = None
    color: Optional[str] = None
    budget_allocated: Optional[float] = None
    budget_executed: Optional[float] = None


class GanttTaskResponse(GanttTaskBase):
    """Full task response with computed fields."""
    id: int
    wp_id: Optional[int]
    wbs_code: Optional[str]
    status: str
    is_readonly: bool
    created_at: datetime
    updated_at: Optional[datetime]

    # DHTMLX specific fields
    open: bool = True  # For tree view expansion

    # Computed alert indicator
    has_alert: bool = False
    alert_type: Optional[str] = None

    class Config:
        from_attributes = True


class GanttLinkBase(BaseModel):
    """Base schema for task links/dependencies."""
    source_id: int = Field(..., alias="source")
    target_id: int = Field(..., alias="target")
    link_type: str = "0"  # 0=FS, 1=SS, 2=FF, 3=SF

    class Config:
        populate_by_name = True


class GanttLinkCreate(GanttLinkBase):
    """Schema for creating a link."""
    pass


class GanttLinkResponse(GanttLinkBase):
    """Link response."""
    id: int

    class Config:
        from_attributes = True
        populate_by_name = True


class DHtmlxGanttData(BaseModel):
    """DHTMLX Gantt compatible response format."""
    data: List[dict]  # Tasks
    links: List[dict]  # Dependencies


class GanttAlertResponse(BaseModel):
    """Alert response."""
    id: int
    task_id: int
    task_text: str
    alert_type: str
    severity: str
    message: str
    budget_variance: Optional[float]
    progress_variance: Optional[float]
    is_acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===================
# TASK ENDPOINTS
# ===================

@router.get("/tasks", response_model=DHtmlxGanttData)
async def get_gantt_data(
    wp_id: Optional[int] = Query(None, description="Filter by Work Package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all Gantt tasks in DHTMLX-compatible format.

    Returns tasks and links formatted for direct use with DHTMLX Gantt.
    """
    query = db.query(GanttTask).options(
        joinedload(GanttTask.owner),
        joinedload(GanttTask.alerts)
    )

    if wp_id:
        query = query.filter(GanttTask.wp_id == wp_id)

    tasks = query.order_by(GanttTask.sort_order, GanttTask.id).all()

    # Format for DHTMLX
    data = []
    for task in tasks:
        has_alert = len(task.alerts) > 0 and any(not a.is_acknowledged for a in task.alerts)
        alert_type = None
        if has_alert:
            # Get most severe unacknowledged alert
            unack_alerts = [a for a in task.alerts if not a.is_acknowledged]
            if unack_alerts:
                alert_type = unack_alerts[0].alert_type.value

        data.append({
            "id": task.id,
            "text": task.text,
            "start_date": task.start_date.strftime("%Y-%m-%d %H:%M"),
            "end_date": task.end_date.strftime("%Y-%m-%d %H:%M"),
            "duration": task.duration,
            "progress": task.progress,
            "parent": task.parent_id or 0,
            "open": True,
            "type": task.task_type,
            "status": task.status.value,
            "wbs_code": task.wbs_code,
            "owner_id": task.owner_id,
            "owner_name": task.owner.full_name if task.owner else None,
            "budget_allocated": task.budget_allocated,
            "budget_executed": task.budget_executed,
            "color": task.color,
            "readonly": task.is_readonly,
            "has_alert": has_alert,
            "alert_type": alert_type,
            # Custom columns for DHTMLX
            "$has_child": len(task.children) > 0 if hasattr(task, 'children') else False
        })

    # Get links
    link_query = db.query(GanttLink)
    if wp_id:
        # Filter links to only include tasks from this WP
        task_ids = [t.id for t in tasks]
        link_query = link_query.filter(
            and_(
                GanttLink.source_id.in_(task_ids),
                GanttLink.target_id.in_(task_ids)
            )
        )

    links = link_query.all()
    links_data = [
        {
            "id": link.id,
            "source": link.source_id,
            "target": link.target_id,
            "type": link.link_type
        }
        for link in links
    ]

    return DHtmlxGanttData(data=data, links=links_data)


@router.get("/tasks/{task_id}", response_model=GanttTaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single task by ID."""
    task = db.query(GanttTask).filter(GanttTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/tasks", response_model=GanttTaskResponse)
async def create_task(
    task_data: GanttTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new Gantt task."""
    # Calculate duration if not provided
    duration = task_data.duration
    if not duration:
        duration = (task_data.end_date - task_data.start_date).days

    task = GanttTask(
        text=task_data.text,
        start_date=task_data.start_date,
        end_date=task_data.end_date,
        duration=max(duration, 1),
        progress=task_data.progress,
        parent_id=task_data.parent_id,
        wp_id=task_data.wp_id,
        task_type=task_data.task_type,
        priority=task_data.priority,
        owner_id=task_data.owner_id,
        notes=task_data.notes,
        color=task_data.color,
        budget_allocated=task_data.budget_allocated,
        budget_executed=task_data.budget_executed,
        created_by=current_user.id
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.put("/tasks/{task_id}", response_model=GanttTaskResponse)
async def update_task(
    task_id: int,
    task_data: GanttTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a Gantt task.

    Used by DHTMLX when dragging tasks or editing inline.
    Implements "Engineering Inverse" by blocking edits to past tasks.
    """
    task = db.query(GanttTask).filter(GanttTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Engineering Inverse: Block edits to completed past tasks
    if task.is_readonly:
        raise HTTPException(
            status_code=403,
            detail="This task is locked and cannot be modified (historical data protection)"
        )

    # Update fields if provided
    update_data = task_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "status" and value:
            value = GanttTaskStatus(value)
        setattr(task, field, value)

    # Recalculate duration if dates changed
    if task_data.start_date or task_data.end_date:
        task.duration = (task.end_date - task.start_date).days

    # Update status based on progress
    if task_data.progress is not None:
        if task.progress >= 1.0:
            task.status = GanttTaskStatus.COMPLETED
        elif task.progress > 0:
            task.status = GanttTaskStatus.IN_PROGRESS
            # Check if late
            if task.end_date and datetime.now() > task.end_date:
                task.status = GanttTaskStatus.LATE

    db.commit()
    db.refresh(task)

    return task


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a task and its children (cascade)."""
    task = db.query(GanttTask).filter(GanttTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.is_readonly:
        raise HTTPException(
            status_code=403,
            detail="This task is locked and cannot be deleted"
        )

    db.delete(task)
    db.commit()

    return {"success": True, "deleted_id": task_id}


# ===================
# LINK ENDPOINTS
# ===================

@router.post("/links", response_model=GanttLinkResponse)
async def create_link(
    link_data: GanttLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a dependency link between tasks."""
    link = GanttLink(
        source_id=link_data.source_id,
        target_id=link_data.target_id,
        link_type=link_data.link_type
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return link


@router.delete("/links/{link_id}")
async def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a dependency link."""
    link = db.query(GanttLink).filter(GanttLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    db.delete(link)
    db.commit()

    return {"success": True, "deleted_id": link_id}


# ===================
# IMPORT ENDPOINTS
# ===================

@router.post("/import")
async def import_excel(
    file: UploadFile = File(...),
    wp_id: Optional[int] = Form(None),
    clear_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import tasks from an Excel matrix file.

    The Excel should have:
    - Month columns with 'x' markers for task duration
    - Task names with hierarchy indicators (indentation, numbering)
    - Optional "Achievement %" column for progress
    """
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        service = GanttImportService(db, base_year=2025)
        result = service.import_excel(
            file_path=tmp_path,
            wp_id=wp_id,
            user_id=current_user.id,
            clear_existing=clear_existing
        )

        return result

    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@router.post("/import/preview")
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview what would be imported without actually saving.

    Useful for validation before committing the import.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        service = GanttImportService(db, base_year=2025)
        result = service.preview_import(tmp_path)
        return result

    finally:
        os.unlink(tmp_path)


# ===================
# ALERT ENDPOINTS
# ===================

@router.get("/alerts", response_model=List[GanttAlertResponse])
async def get_alerts(
    wp_id: Optional[int] = Query(None),
    unacknowledged_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project health alerts."""
    query = db.query(GanttAlert).join(GanttTask)

    if wp_id:
        query = query.filter(GanttTask.wp_id == wp_id)

    if unacknowledged_only:
        query = query.filter(GanttAlert.is_acknowledged == False)

    alerts = query.order_by(GanttAlert.created_at.desc()).all()

    return [
        GanttAlertResponse(
            id=a.id,
            task_id=a.task_id,
            task_text=a.task.text,
            alert_type=a.alert_type.value,
            severity=a.severity,
            message=a.message,
            budget_variance=a.budget_variance,
            progress_variance=a.progress_variance,
            is_acknowledged=a.is_acknowledged,
            created_at=a.created_at
        )
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an alert."""
    alert = db.query(GanttAlert).filter(GanttAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now()

    db.commit()

    return {"success": True}


@router.post("/check-health")
async def run_health_check(
    wp_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run project health check and generate alerts.

    Checks for:
    - Tasks due soon (preventive alerts)
    - Overdue tasks (late alerts)
    - Budget vs progress discrepancies (financial alerts)
    """
    from services.gantt_health_service import check_project_health

    result = check_project_health(db, wp_id)
    return result


@router.get("/health-summary")
async def get_health_summary(
    wp_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get project health summary without generating new alerts.

    Returns overall health score, task status breakdown, and budget utilization.
    """
    from services.gantt_health_service import get_project_health_summary

    result = get_project_health_summary(db, wp_id)
    return result


# ===================
# WORK PACKAGE ENDPOINTS
# ===================

@router.get("/work-packages")
async def get_work_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all work packages with task counts."""
    wps = db.query(WorkPackage).all()

    result = []
    for wp in wps:
        task_count = db.query(GanttTask).filter(GanttTask.wp_id == wp.id).count()
        result.append({
            "id": wp.id,
            "name": wp.name,
            "task_count": task_count
        })

    return result


@router.get("/import-logs")
async def get_import_logs(
    wp_id: Optional[int] = Query(None),
    limit: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import history."""
    query = db.query(GanttImportLog)

    if wp_id:
        query = query.filter(GanttImportLog.wp_id == wp_id)

    logs = query.order_by(GanttImportLog.imported_at.desc()).limit(limit).all()

    return [
        {
            "id": log.id,
            "filename": log.filename,
            "wp_id": log.wp_id,
            "tasks_created": log.tasks_created,
            "tasks_updated": log.tasks_updated,
            "errors_count": log.errors_count,
            "imported_at": log.imported_at.isoformat() if log.imported_at else None
        }
        for log in logs
    ]
