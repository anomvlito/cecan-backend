"""
Seed Script: Assign RACI Responsibilities from Real Gantt Data

This script creates RACI assignments based on REAL ProjectActivity and
ScientificProject data from the Gantt, NOT simulated/fake activities.

Key Principle: Gantt = Source of Truth

Usage:
    python scripts/seed_responsibilities_from_gantt.py
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import get_session
from core.models import (
    ResponsibilityAssignment, ResourceType, RaciRole,
    AcademicMember, ScientificProject, ProjectActivity, User, UserRole
)


def clear_existing_assignments(db):
    """Clear all existing RACI assignments to start fresh."""
    print("🗑️  Clearing existing assignments...")
    count = db.query(ResponsibilityAssignment).delete()
    db.commit()
    print(f"   Deleted {count} old assignments\n")


def assign_pi_to_projects(db, admin_user):
    """Assign PIs as Accountable for their projects."""
    print("📋 Step 1: Assigning PIs to their projects...")
    count = 0

    projects_with_pi = db.query(ScientificProject).filter(
        ScientificProject.pi_id.isnot(None)
    ).all()

    for project in projects_with_pi:
        # Check if assignment already exists
        existing = db.query(ResponsibilityAssignment).filter_by(
            resource_type=ResourceType.SCIENTIFIC_PROJECT,
            resource_id=project.id,
            member_id=project.pi_id,
            raci_role=RaciRole.A
        ).first()

        if not existing:
            # Get PI's user_id if exists
            pi_member = db.query(AcademicMember).filter_by(id=project.pi_id).first()
            user_id = None
            if pi_member and pi_member.email:
                user = db.query(User).filter_by(email=pi_member.email).first()
                if user:
                    user_id = user.id

            assignment = ResponsibilityAssignment(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                raci_role=RaciRole.A,
                member_id=project.pi_id,
                user_id=user_id,
                created_by=admin_user.id if admin_user else None
            )
            db.add(assignment)
            count += 1
            print(f"   ✓ PI (member #{project.pi_id}) → Accountable for project {project.code}")

    db.commit()
    print(f"   Total: {count} project assignments\n")
    return count


def assign_demo_researcher(db, admin_user):
    """Assign researcher@cecan.cl to real activities from different projects."""
    print("📋 Step 2: Assigning researcher@cecan.cl to activities...")
    count = 0

    # Find researcher user and member
    researcher_user = db.query(User).filter_by(email="researcher@cecan.cl").first()
    if not researcher_user:
        print("   ⚠️  researcher@cecan.cl not found, skipping")
        return 0

    researcher_member = db.query(AcademicMember).filter_by(email=researcher_user.email).first()
    if not researcher_member:
        print("   ⚠️  researcher member not found, skipping")
        return 0

    # Get real activities from different projects (limit 5)
    # Prefer activities from P-04 and P-02 (research-heavy projects)
    activities = db.query(ProjectActivity).join(ScientificProject).filter(
        ScientificProject.code.in_(['P-04', 'P-02', 'DP-01'])
    ).limit(5).all()

    for activity in activities:
        # Check if assignment already exists
        existing = db.query(ResponsibilityAssignment).filter_by(
            resource_type=ResourceType.PROJECT_ACTIVITY,
            resource_id=activity.id,
            member_id=researcher_member.id,
            raci_role=RaciRole.R
        ).first()

        if not existing:
            assignment = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=activity.id,
                raci_role=RaciRole.R,
                member_id=researcher_member.id,
                user_id=researcher_user.id,
                created_by=admin_user.id if admin_user else None
            )
            db.add(assignment)
            count += 1

            # Get project for display
            project = activity.project
            print(f"   ✓ Activity #{activity.id} ({activity.description[:50]}...)")
            print(f"     Project: {project.code if project else 'N/A'}")

    db.commit()
    print(f"   Total: {count} activity assignments for researcher\n")
    return count


def assign_demo_staff(db, admin_user):
    """Assign staff@cecan.cl as Accountable for administrative activities."""
    print("📋 Step 3: Assigning staff@cecan.cl to administrative activities...")
    count = 0

    # Find staff user and member
    staff_user = db.query(User).filter_by(email="staff@cecan.cl").first()
    if not staff_user:
        print("   ⚠️  staff@cecan.cl not found, skipping")
        return 0

    staff_member = db.query(AcademicMember).filter_by(email=staff_user.email).first()
    if not staff_member:
        print("   ⚠️  staff member not found, skipping")
        return 0

    # Get activities from P-02 (biobanking/governance - administrative)
    activities = db.query(ProjectActivity).join(ScientificProject).filter(
        ScientificProject.code == 'P-02'
    ).limit(3).all()

    for activity in activities:
        existing = db.query(ResponsibilityAssignment).filter_by(
            resource_type=ResourceType.PROJECT_ACTIVITY,
            resource_id=activity.id,
            member_id=staff_member.id,
            raci_role=RaciRole.A
        ).first()

        if not existing:
            assignment = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=activity.id,
                raci_role=RaciRole.A,
                member_id=staff_member.id,
                user_id=staff_user.id,
                created_by=admin_user.id if admin_user else None
            )
            db.add(assignment)
            count += 1
            print(f"   ✓ Activity #{activity.id} ({activity.description[:50]}...)")

    db.commit()
    print(f"   Total: {count} activity assignments for staff\n")
    return count


def assign_demo_student(db, admin_user):
    """Assign student@cecan.cl to activities (e.g., thesis-related work)."""
    print("📋 Step 4: Assigning student@cecan.cl to activities...")
    count = 0

    # Find student user and member
    student_user = db.query(User).filter_by(email="student@cecan.cl").first()
    if not student_user:
        print("   ⚠️  student@cecan.cl not found, skipping")
        return 0

    student_member = db.query(AcademicMember).filter_by(email=student_user.email).first()
    if not student_member:
        print("   ⚠️  student member not found, skipping")
        return 0

    # Get 2 activities from different projects
    activities = db.query(ProjectActivity).join(ScientificProject).filter(
        ScientificProject.code.in_(['P-04', 'DP-01'])
    ).limit(2).all()

    for activity in activities:
        existing = db.query(ResponsibilityAssignment).filter_by(
            resource_type=ResourceType.PROJECT_ACTIVITY,
            resource_id=activity.id,
            member_id=student_member.id,
            raci_role=RaciRole.R
        ).first()

        if not existing:
            assignment = ResponsibilityAssignment(
                resource_type=ResourceType.PROJECT_ACTIVITY,
                resource_id=activity.id,
                raci_role=RaciRole.R,
                member_id=student_member.id,
                user_id=student_user.id,
                created_by=admin_user.id if admin_user else None
            )
            db.add(assignment)
            count += 1

            project = activity.project
            print(f"   ✓ Activity #{activity.id} ({activity.description[:50]}...)")
            print(f"     Project: {project.code if project else 'N/A'}")

    db.commit()
    print(f"   Total: {count} activity assignments for student\n")
    return count


def verify_all_real(db):
    """Verify that all assignments point to REAL Gantt activities/projects."""
    print("🔍 Verifying all assignments point to REAL resources...")

    assignments = db.query(ResponsibilityAssignment).all()
    all_valid = True

    for assignment in assignments:
        if assignment.resource_type == ResourceType.PROJECT_ACTIVITY:
            activity = db.query(ProjectActivity).filter_by(id=assignment.resource_id).first()
            if not activity:
                print(f"   ❌ Assignment #{assignment.id} → Activity #{assignment.resource_id} (NOT FOUND)")
                all_valid = False
        elif assignment.resource_type == ResourceType.SCIENTIFIC_PROJECT:
            project = db.query(ScientificProject).filter_by(id=assignment.resource_id).first()
            if not project:
                print(f"   ❌ Assignment #{assignment.id} → Project #{assignment.resource_id} (NOT FOUND)")
                all_valid = False

    if all_valid:
        print("   ✅ All assignments verified - they point to REAL Gantt resources\n")
    else:
        print("   ⚠️  Some assignments are invalid!\n")

    return all_valid


def print_summary(db):
    """Print summary of assignments created."""
    print("\n" + "="*70)
    print("📊 ASSIGNMENT SUMMARY")
    print("="*70)

    # By resource type
    print("\nBy Resource Type:")
    for resource_type in ResourceType:
        count = db.query(ResponsibilityAssignment).filter_by(
            resource_type=resource_type
        ).count()
        if count > 0:
            print(f"  {resource_type.value}: {count}")

    # By RACI role
    print("\nBy RACI Role:")
    for raci_role in RaciRole:
        count = db.query(ResponsibilityAssignment).filter_by(
            raci_role=raci_role
        ).count()
        if count > 0:
            print(f"  {raci_role.value} ({raci_role.name}): {count}")

    # By user
    print("\nBy Demo User:")
    for email in ['researcher@cecan.cl', 'staff@cecan.cl', 'student@cecan.cl', 'pi@cecan.cl']:
        user = db.query(User).filter_by(email=email).first()
        if user:
            count = db.query(ResponsibilityAssignment).filter_by(user_id=user.id).count()
            print(f"  {email}: {count} assignments")

    # Total
    total = db.query(ResponsibilityAssignment).count()
    print(f"\n📊 Total Assignments: {total}")
    print("="*70)

    print("\n✨ All assignments are based on REAL Gantt activities!")
    print("💡 Test the dashboard with:")
    print("   - researcher@cecan.cl / res123")
    print("   - staff@cecan.cl / staff123")
    print("   - student@cecan.cl / stu123")


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("🎯 SEEDING RACI ASSIGNMENTS FROM REAL GANTT DATA")
    print("="*70)
    print("\nPrinciple: Gantt = Source of Truth")
    print("All assignments will point to REAL ProjectActivity/ScientificProject\n")

    db = get_session()
    try:
        # Get admin user for created_by
        admin_user = db.query(User).filter_by(role=UserRole.ADMIN).first()

        # Clear old assignments
        clear_existing_assignments(db)

        # Assign based on real Gantt data
        pi_count = assign_pi_to_projects(db, admin_user)
        researcher_count = assign_demo_researcher(db, admin_user)
        staff_count = assign_demo_staff(db, admin_user)
        student_count = assign_demo_student(db, admin_user)

        # Verify integrity
        verify_all_real(db)

        # Summary
        print_summary(db)

        print("\n🎉 Seeding complete!")
        print("🔗 Gantt and 'Mis Tareas' are now connected via REAL activities\n")

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
