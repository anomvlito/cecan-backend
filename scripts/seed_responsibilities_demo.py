"""
Seed Script: Demo Responsibility Assignments

This script creates sample RACI responsibility assignments for testing the
authorization system. It assigns roles to academic members for projects,
activities, and publications.

Usage:
    python scripts/seed_responsibilities_demo.py
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database.session import get_session
from core.models import (
    ResponsibilityAssignment, ResourceType, RaciRole,
    AcademicMember, ScientificProject, User, UserRole
)


def seed_demo_responsibilities(db: Session):
    """
    Create demo responsibility assignments.

    This script:
    1. Finds existing projects and members
    2. Assigns RACI roles to members for testing
    3. Creates realistic scenarios for different user roles
    """
    print("\n=== Seeding Demo Responsibility Assignments ===\n")

    # Get some existing projects
    projects = db.query(ScientificProject).limit(5).all()
    if not projects:
        print("⚠️  No projects found. Please create some projects first.")
        return

    # Get some existing members
    members = db.query(AcademicMember).filter_by(is_active=True).limit(10).all()
    if not members:
        print("⚠️  No academic members found. Please create some members first.")
        return

    # Get admin user for created_by field
    admin_user = db.query(User).filter_by(role=UserRole.ADMIN).first()
    if not admin_user:
        admin_user = db.query(User).first()

    created_count = 0

    # Scenario 1: Assign Accountable (A) role to PIs for their projects
    print("📋 Scenario 1: Assigning Accountable roles to PIs...")
    for project in projects[:3]:
        if project.pi_id:
            # Check if assignment already exists
            existing = db.query(ResponsibilityAssignment).filter_by(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                member_id=project.pi_id,
                raci_role=RaciRole.A
            ).first()

            if not existing:
                assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.SCIENTIFIC_PROJECT,
                    resource_id=project.id,
                    member_id=project.pi_id,
                    raci_role=RaciRole.A,
                    created_by=admin_user.id if admin_user else None
                )
                db.add(assignment)
                created_count += 1
                print(f"  ✓ Assigned Accountable role for project '{project.title}' to member ID {project.pi_id}")

    # Scenario 2: Assign Responsible (R) role to other researchers
    print("\n📋 Scenario 2: Assigning Responsible roles to researchers...")
    for i, project in enumerate(projects[:3]):
        if i < len(members) - 1:
            member = members[i + 1]  # Use different member than PI

            # Check if assignment already exists
            existing = db.query(ResponsibilityAssignment).filter_by(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                member_id=member.id,
                raci_role=RaciRole.R
            ).first()

            if not existing and member.id != project.pi_id:
                assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.SCIENTIFIC_PROJECT,
                    resource_id=project.id,
                    member_id=member.id,
                    raci_role=RaciRole.R,
                    created_by=admin_user.id if admin_user else None
                )
                db.add(assignment)
                created_count += 1
                print(f"  ✓ Assigned Responsible role for project '{project.title}' to {member.full_name}")

    # Scenario 3: Assign Consulted (C) role to consultants
    print("\n📋 Scenario 3: Assigning Consulted roles...")
    for i, project in enumerate(projects[:2]):
        if i + 2 < len(members):
            member = members[i + 2]

            # Check if assignment already exists
            existing = db.query(ResponsibilityAssignment).filter_by(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                member_id=member.id,
                raci_role=RaciRole.C
            ).first()

            if not existing:
                assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.SCIENTIFIC_PROJECT,
                    resource_id=project.id,
                    member_id=member.id,
                    raci_role=RaciRole.C,
                    created_by=admin_user.id if admin_user else None
                )
                db.add(assignment)
                created_count += 1
                print(f"  ✓ Assigned Consulted role for project '{project.title}' to {member.full_name}")

    # Scenario 4: Assign Informed (I) role to stakeholders
    print("\n📋 Scenario 4: Assigning Informed roles to stakeholders...")
    for i, project in enumerate(projects[:2]):
        if i + 3 < len(members):
            member = members[i + 3]

            # Check if assignment already exists
            existing = db.query(ResponsibilityAssignment).filter_by(
                resource_type=ResourceType.SCIENTIFIC_PROJECT,
                resource_id=project.id,
                member_id=member.id,
                raci_role=RaciRole.I
            ).first()

            if not existing:
                assignment = ResponsibilityAssignment(
                    resource_type=ResourceType.SCIENTIFIC_PROJECT,
                    resource_id=project.id,
                    member_id=member.id,
                    raci_role=RaciRole.I,
                    created_by=admin_user.id if admin_user else None
                )
                db.add(assignment)
                created_count += 1
                print(f"  ✓ Assigned Informed role for project '{project.title}' to {member.full_name}")

    # Commit all changes
    db.commit()

    print(f"\n✅ Created {created_count} new responsibility assignments")
    print("\n=== Summary ===")
    total_assignments = db.query(ResponsibilityAssignment).count()
    print(f"Total responsibility assignments in database: {total_assignments}")

    # Show breakdown by RACI role
    for role in RaciRole:
        count = db.query(ResponsibilityAssignment).filter_by(raci_role=role).count()
        print(f"  {role.value} ({"Accountable" if role == RaciRole.A else "Responsible" if role == RaciRole.R else "Consulted" if role == RaciRole.C else "Informed"}): {count}")

    print("\n🎉 Seeding complete!")


def main():
    """Main entry point for the script."""
    print("Starting responsibility assignment seeding...")

    db = next(get_session())
    try:
        seed_demo_responsibilities(db)
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
