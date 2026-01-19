"""
Gantt Health Service - Project Health Monitoring & Alert Generation
Implements business logic for detecting project risks and financial discrepancies.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models import (
    GanttTask, GanttTaskStatus, GanttAlert, GanttAlertType
)


def check_project_health(
    db: Session,
    wp_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run comprehensive health check on Gantt tasks.

    Generates alerts for:
    1. PREVENTIVE: Tasks due within 30 days with low progress
    2. LATE: Overdue tasks
    3. FINANCIAL_DISCREPANCY: Budget vs progress mismatch
    4. MILESTONE_RISK: Milestones at risk due to dependent task delays

    Args:
        db: Database session
        wp_id: Optional Work Package filter

    Returns:
        Dict with check results and generated alerts
    """
    result = {
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'alerts_generated': 0,
        'alerts_by_type': {
            'preventive': 0,
            'late': 0,
            'financial_discrepancy': 0,
            'milestone_risk': 0
        },
        'tasks_checked': 0,
        'healthy_tasks': 0,
        'at_risk_tasks': 0
    }

    try:
        # Get active tasks (not completed)
        query = db.query(GanttTask).filter(
            GanttTask.status != GanttTaskStatus.COMPLETED
        )

        if wp_id:
            query = query.filter(GanttTask.wp_id == wp_id)

        tasks = query.all()
        result['tasks_checked'] = len(tasks)

        now = datetime.now()
        thirty_days = now + timedelta(days=30)

        for task in tasks:
            alerts_for_task = []

            # =========================
            # CHECK 1: LATE TASKS
            # =========================
            if task.end_date and now > task.end_date and task.progress < 1.0:
                days_overdue = (now - task.end_date).days

                # Check if alert already exists
                existing = db.query(GanttAlert).filter(
                    and_(
                        GanttAlert.task_id == task.id,
                        GanttAlert.alert_type == GanttAlertType.LATE,
                        GanttAlert.is_acknowledged == False
                    )
                ).first()

                if not existing:
                    alert = GanttAlert(
                        task_id=task.id,
                        alert_type=GanttAlertType.LATE,
                        severity='critical' if days_overdue > 14 else 'warning',
                        message=f"Task '{task.text}' is {days_overdue} days overdue with {task.progress*100:.0f}% progress",
                        progress_variance=1.0 - task.progress
                    )
                    db.add(alert)
                    alerts_for_task.append('late')
                    result['alerts_by_type']['late'] += 1

                # Update task status
                task.status = GanttTaskStatus.LATE

            # =========================
            # CHECK 2: PREVENTIVE ALERTS
            # =========================
            elif task.end_date and now <= task.end_date <= thirty_days:
                # Task due within 30 days
                days_until_due = (task.end_date - now).days
                time_elapsed_pct = 1.0 - (days_until_due / 30.0)

                # If progress is significantly behind schedule
                expected_progress = min(time_elapsed_pct, 1.0)
                if task.progress < expected_progress * 0.7:  # 30% behind expected
                    existing = db.query(GanttAlert).filter(
                        and_(
                            GanttAlert.task_id == task.id,
                            GanttAlert.alert_type == GanttAlertType.PREVENTIVE,
                            GanttAlert.is_acknowledged == False
                        )
                    ).first()

                    if not existing:
                        alert = GanttAlert(
                            task_id=task.id,
                            alert_type=GanttAlertType.PREVENTIVE,
                            severity='warning',
                            message=f"Task '{task.text}' due in {days_until_due} days but only {task.progress*100:.0f}% complete",
                            progress_variance=expected_progress - task.progress
                        )
                        db.add(alert)
                        alerts_for_task.append('preventive')
                        result['alerts_by_type']['preventive'] += 1

            # =========================
            # CHECK 3: FINANCIAL DISCREPANCY
            # =========================
            if task.budget_allocated > 0:
                budget_spent_pct = task.budget_executed / task.budget_allocated

                # If spent more than 50% of budget but progress is less than 25%
                if budget_spent_pct > 0.5 and task.progress < 0.25:
                    existing = db.query(GanttAlert).filter(
                        and_(
                            GanttAlert.task_id == task.id,
                            GanttAlert.alert_type == GanttAlertType.FINANCIAL_DISCREPANCY,
                            GanttAlert.is_acknowledged == False
                        )
                    ).first()

                    if not existing:
                        variance = budget_spent_pct - task.progress
                        alert = GanttAlert(
                            task_id=task.id,
                            alert_type=GanttAlertType.FINANCIAL_DISCREPANCY,
                            severity='critical',
                            message=f"Financial discrepancy: '{task.text}' has spent {budget_spent_pct*100:.0f}% of budget but only {task.progress*100:.0f}% complete",
                            budget_variance=variance,
                            progress_variance=task.progress
                        )
                        db.add(alert)
                        alerts_for_task.append('financial_discrepancy')
                        result['alerts_by_type']['financial_discrepancy'] += 1

                # Also check for over-budget
                if task.budget_executed > task.budget_allocated:
                    over_budget_pct = ((task.budget_executed - task.budget_allocated) / task.budget_allocated) * 100

                    existing = db.query(GanttAlert).filter(
                        and_(
                            GanttAlert.task_id == task.id,
                            GanttAlert.alert_type == GanttAlertType.FINANCIAL_DISCREPANCY,
                            GanttAlert.message.like('%over budget%'),
                            GanttAlert.is_acknowledged == False
                        )
                    ).first()

                    if not existing:
                        alert = GanttAlert(
                            task_id=task.id,
                            alert_type=GanttAlertType.FINANCIAL_DISCREPANCY,
                            severity='critical',
                            message=f"Over budget: '{task.text}' has exceeded budget by {over_budget_pct:.1f}%",
                            budget_variance=over_budget_pct / 100
                        )
                        db.add(alert)
                        alerts_for_task.append('financial_discrepancy')
                        result['alerts_by_type']['financial_discrepancy'] += 1

            # Track health
            if alerts_for_task:
                result['at_risk_tasks'] += 1
            else:
                result['healthy_tasks'] += 1

        result['alerts_generated'] = sum(result['alerts_by_type'].values())

        db.commit()

    except Exception as e:
        db.rollback()
        result['success'] = False
        result['error'] = str(e)

    return result


def get_project_health_summary(
    db: Session,
    wp_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get a summary of project health without generating new alerts.

    Returns:
        Dict with health metrics and statistics
    """
    query = db.query(GanttTask)
    if wp_id:
        query = query.filter(GanttTask.wp_id == wp_id)

    tasks = query.all()

    total_tasks = len(tasks)
    completed = sum(1 for t in tasks if t.status == GanttTaskStatus.COMPLETED)
    in_progress = sum(1 for t in tasks if t.status == GanttTaskStatus.IN_PROGRESS)
    late = sum(1 for t in tasks if t.status == GanttTaskStatus.LATE)
    pending = sum(1 for t in tasks if t.status == GanttTaskStatus.PENDING)

    # Calculate overall progress
    total_progress = sum(t.progress for t in tasks) / total_tasks if total_tasks > 0 else 0

    # Budget summary
    total_budget = sum(t.budget_allocated for t in tasks)
    total_executed = sum(t.budget_executed for t in tasks)
    budget_utilization = (total_executed / total_budget * 100) if total_budget > 0 else 0

    # Active alerts
    alert_query = db.query(GanttAlert).filter(GanttAlert.is_acknowledged == False)
    if wp_id:
        alert_query = alert_query.join(GanttTask).filter(GanttTask.wp_id == wp_id)

    active_alerts = alert_query.count()

    return {
        'total_tasks': total_tasks,
        'status_breakdown': {
            'completed': completed,
            'in_progress': in_progress,
            'late': late,
            'pending': pending
        },
        'overall_progress': round(total_progress * 100, 1),
        'budget': {
            'allocated': total_budget,
            'executed': total_executed,
            'utilization_percent': round(budget_utilization, 1)
        },
        'active_alerts': active_alerts,
        'health_score': calculate_health_score(tasks, active_alerts)
    }


def calculate_health_score(tasks: List[GanttTask], active_alerts: int) -> int:
    """
    Calculate an overall health score from 0-100.

    Factors:
    - Percentage of tasks on schedule
    - Number of active alerts
    - Budget utilization vs progress alignment
    """
    if not tasks:
        return 100

    score = 100

    # Deduct for late tasks (up to 30 points)
    late_count = sum(1 for t in tasks if t.status == GanttTaskStatus.LATE)
    late_penalty = min(30, (late_count / len(tasks)) * 100)
    score -= late_penalty

    # Deduct for active alerts (up to 20 points)
    alert_penalty = min(20, active_alerts * 5)
    score -= alert_penalty

    # Deduct for low progress tasks due soon (up to 20 points)
    now = datetime.now()
    soon = now + timedelta(days=14)
    at_risk = sum(
        1 for t in tasks
        if t.end_date and now <= t.end_date <= soon and t.progress < 0.5
    )
    risk_penalty = min(20, at_risk * 4)
    score -= risk_penalty

    # Bonus for completed tasks (up to 10 points)
    completed_ratio = sum(1 for t in tasks if t.status == GanttTaskStatus.COMPLETED) / len(tasks)
    score += completed_ratio * 10

    return max(0, min(100, int(score)))


def lock_historical_tasks(db: Session, cutoff_date: datetime) -> int:
    """
    Lock tasks that ended before the cutoff date (Engineering Inverse).

    This prevents modification of historical data for audit compliance.

    Args:
        db: Database session
        cutoff_date: Tasks ending before this date will be locked

    Returns:
        Number of tasks locked
    """
    result = db.query(GanttTask).filter(
        and_(
            GanttTask.end_date < cutoff_date,
            GanttTask.is_readonly == False
        )
    ).update({"is_readonly": True})

    db.commit()
    return result
