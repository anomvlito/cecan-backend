"""
Seed Script: Interactive Responsibility Assignments

This script creates comprehensive RACI responsibility assignments for testing
the My Responsibilities dashboard. It assigns roles to academic members for
both projects AND activities, with realistic scenarios including overdue items.

Usage:
    python scripts/seed_responsibilities_interactive.py
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database.session import get_session
from core.models import (
    ResponsibilityAssignment, ResourceType, RaciRole,
    AcademicMember, ScientificProject, ProjectActivity, User, UserRole,
    ActivityStatusType
)


def seed_interactive_responsibilities(db: Session):
    """
    Create comprehensive demo responsibility assignments.

    This script:
    1. Finds existing projects, activities, and members
    2. Assigns RACI roles with user_id linking (via email match)
    3. Creates realistic scenarios including overdue items
    4. Tests different user role scenarios
    """
    print("\n=== Seeding Interactive Responsibility Assignments ===\n")

    # Get existing resources
    projects = db.query(ScientificProject).limit(5).all()
    activities = db.query(ProjectActivity).limit(10).all()
    members = db.query(AcademicMember).filter_by(is_active=True).all()
    users = db.query(User).all()

    if not projects:
        print("⚠️  No projects found. Please create some projects first.")
        return

    if not members:
        print("⚠️  No academic members found. Please create some members first.")
        return

    # Create email-to-user mapping for linking user_id
    email_to_user = {user.email: user for user in users}

    # Get admin user for created_by field
    admin_user = db.query(User).filter_by(role=UserRole.ADMIN).first()
    if not admin_user:
        admin_user = users[0] if users else None

    created_count = 0

    # Helper function to create assignment with user_id linking
    def create_assignment(resource_type, resource_id, member, raci_role, description):
        nonlocal created_count

        # Check if assignment already exists
        existing = db.query(ResponsibilityAssignment).filter_by(
            resource_type=resource_type,
            resource_id=resource_id,
            member_id=member.id,
            raci_role=raci_role
        ).first()

        if existing:
            print(f"  ⏭️  {description} (already exists)")
            return

        # Try to link user_id via email match
        user_id = None
        if member.email and member.email in email_to_user:
            user_id = email_to_user[member.email].id

        assignment = ResponsibilityAssignment(
            resource_type=resource_type,
            resource_id=resource_id,
            member_id=member.id,
            user_id=user_id,
            raci_role=raci_role,
            created_by=admin_user.id if admin_user else None
        )
        db.add(assignment)
        created_count += 1
        user_link = f" (linked to user {user_id})" if user_id else ""
        print(f"  ✓ {description}{user_link}")

    # ===========================
    # SCENARIO 1: PI Projects
    # ===========================
    print("\n📋 Scenario 1: PI Projects (Accountable)")
    for project in projects[:3]:
        if project.pi_id:
            pi_member = db.query(AcademicMember).filter_by(id=project.pi_id).first()
            if pi_member:
                create_assignment(
                    ResourceType.SCIENTIFIC_PROJECT,
                    project.id,
                    pi_member,
                    RaciRole.A,
                    f"PI '{pi_member.full_name}' accountable for '{project.title}'"
                )

    # ===========================
    # SCENARIO 2: Researcher Activities
    # ===========================
    print("\n📋 Scenario 2: Researcher Activities (Responsible)")

    # Find researchers by email matching to demo users
    researcher_user = db.query(User).filter_by(email="researcher@cecan.cl").first()
    if researcher_user:
        researcher_member = db.query(AcademicMember).filter_by(email=researcher_user.email).first()
        if researcher_member and activities:
            # Assign first 3 activities to researcher
            for activity in activities[:3]:
                create_assignment(
                    ResourceType.PROJECT_ACTIVITY,
                    activity.id,
                    researcher_member,
                    RaciRole.R,
                    f"Researcher responsible for activity: {activity.description[:50]}..."
                )

    # ===========================
    # SCENARIO 3: Staff Activities (Administrative)
    # ===========================
    print("\n📋 Scenario 3: Staff Activities")

    staff_user = db.query(User).filter_by(email="staff@cecan.cl").first()
    if staff_user:
        staff_member = db.query(AcademicMember).filter_by(email=staff_user.email).first()
        if staff_member and activities:
            # Assign activities 3-5 to staff
            for activity in activities[3:6]:
                create_assignment(
                    ResourceType.PROJECT_ACTIVITY,
                    activity.id,
                    staff_member,
                    RaciRole.A,
                    f"Staff accountable for activity: {activity.description[:50]}..."
                )

    # ===========================
    # SCENARIO 4: Student Activities
    # ===========================
    print("\n📋 Scenario 4: Student Activities")

    student_user = db.query(User).filter_by(email="student@cecan.cl").first()
    if student_user:
        student_member = db.query(AcademicMember).filter_by(email=student_user.email).first()
        if student_member and activities:
            # Assign 2 activities to student
            for activity in activities[6:8]:
                create_assignment(
                    ResourceType.PROJECT_ACTIVITY,
                    activity.id,
                    student_member,
                    RaciRole.R,
                    f"Student responsible for activity: {activity.description[:50]}..."
                )

    # ===========================
    # SCENARIO 5: Collaborative Projects
    # ===========================
    print("\n📋 Scenario 5: Collaborative Projects (Multiple Roles)")

    if len(projects) >= 2 and len(members) >= 3:
        project = projects[1]

        # Accountable (PI)
        if project.pi_id:
            pi_member = db.query(AcademicMember).filter_by(id=project.pi_id).first()
            if pi_member:
                create_assignment(
                    ResourceType.SCIENTIFIC_PROJECT,
                    project.id,
                    pi_member,
                    RaciRole.A,
                    f"PI accountable for '{project.title}'"
                )

        # Responsible (Co-investigator)
        if len(members) >= 2 and members[1].id != project.pi_id:
            create_assignment(
                ResourceType.SCIENTIFIC_PROJECT,
                project.id,
                members[1],
                RaciRole.R,
                f"Co-investigator '{members[1].full_name}' responsible for '{project.title}'"
            )

        # Consulted (External advisor)
        if len(members) >= 3 and members[2].id != project.pi_id:
            create_assignment(
                ResourceType.SCIENTIFIC_PROJECT,
                project.id,
                members[2],
                RaciRole.C,
                f"Advisor '{members[2].full_name}' consulted for '{project.title}'"
            )

    # ===========================
    # SCENARIO 6: Create Overdue Activities for Testing
    # ===========================
    print("\n📋 Scenario 6: Creating Overdue Activities for Testing")

    # Set some activities as overdue
    if activities:
        overdue_date = datetime.now().date() - timedelta(days=30)

        for activity in activities[:2]:
            if activity.status != ActivityStatusType.DONE:
                activity.end_month = overdue_date
                activity.status = ActivityStatusType.IN_PROGRESS
                db.add(activity)
                print(f"  ⏰ Set activity '{activity.description[:50]}...' as overdue (end: {overdue_date})")

    # Commit all changes
    db.commit()

    print(f"\n✅ Created {created_count} new responsibility assignments")
    print("\n=== Summary ===")

    # Overall stats
    total_assignments = db.query(ResponsibilityAssignment).count()
    print(f"Total responsibility assignments in database: {total_assignments}")

    # Breakdown by resource type
    print("\nBy Resource Type:")
    for resource_type in ResourceType:
        count = db.query(ResponsibilityAssignment).filter_by(resource_type=resource_type).count()
        if count > 0:
            print(f"  {resource_type.value}: {count}")

    # Breakdown by RACI role
    print("\nBy RACI Role:")
    role_labels = {
        RaciRole.R: "Responsible",
        RaciRole.A: "Accountable",
        RaciRole.C: "Consulted",
        RaciRole.I: "Informed"
    }
    for role in RaciRole:
        count = db.query(ResponsibilityAssignment).filter_by(raci_role=role).count()
        if count > 0:
            print(f"  {role.value} ({role_labels[role]}): {count}")

    # User linkage stats
    print("\nUser Linkage:")
    linked_count = db.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.user_id.isnot(None)
    ).count()
    print(f"  Linked to user accounts: {linked_count}")
    print(f"  Member-only assignments: {total_assignments - linked_count}")

    print("\n🎉 Seeding complete!")
    print("\n💡 Test the dashboard by logging in as:")
    print("   - pi@cecan.cl (should see projects as Accountable)")
    print("   - researcher@cecan.cl (should see activities as Responsible)")
    print("   - staff@cecan.cl (should see activities as Accountable)")
    print("   - student@cecan.cl (should see assigned activities)")


def main():
    """Main entry point for the script."""
    print("Starting interactive responsibility assignment seeding...")

    db = get_session()
    try:
        seed_interactive_responsibilities(db)
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
