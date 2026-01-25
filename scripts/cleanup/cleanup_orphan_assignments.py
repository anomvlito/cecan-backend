"""
Cleanup Script: Remove Orphan Responsibility Assignments

This script removes ResponsibilityAssignments that point to non-existent
ProjectActivity IDs, ensuring referential integrity.

Usage:
    python scripts/cleanup_orphan_assignments.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import get_session
from core.models import ResponsibilityAssignment, ProjectActivity, ResourceType


def cleanup_orphan_assignments(db):
    """
    Remove responsibility assignments pointing to non-existent activities.

    Returns:
        tuple: (total_checked, orphans_removed, remaining)
    """
    print("\n=== Cleaning Orphan Responsibility Assignments ===\n")

    # Get all assignments to project activities
    assignments = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).all()

    total_checked = len(assignments)
    print(f"📋 Total assignments to activities: {total_checked}")

    # Check which ones point to non-existent activities
    orphans = []
    valid = []

    for assignment in assignments:
        activity = db.query(ProjectActivity).filter_by(
            id=assignment.resource_id
        ).first()

        if activity:
            valid.append(assignment)
        else:
            orphans.append(assignment)
            print(f"  ⚠️  Orphan found: Assignment #{assignment.id} → Activity #{assignment.resource_id} (doesn't exist)")

    print(f"\n✅ Valid assignments: {len(valid)}")
    print(f"❌ Orphan assignments: {len(orphans)}")

    if orphans:
        print(f"\n🗑️  Deleting {len(orphans)} orphan assignments...")

        for assignment in orphans:
            db.delete(assignment)

        db.commit()
        print("✅ Orphans deleted successfully")
    else:
        print("\n✨ No orphan assignments found. Database is clean!")

    # Final verification
    remaining = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).count()

    print(f"\n📊 Final count: {remaining} valid assignments remain")

    return total_checked, len(orphans), remaining


def verify_integrity(db):
    """Verify that all remaining assignments point to real activities."""
    print("\n=== Verifying Referential Integrity ===\n")

    assignments = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).all()

    all_valid = True
    for assignment in assignments:
        activity = db.query(ProjectActivity).filter_by(
            id=assignment.resource_id
        ).first()

        if not activity:
            print(f"❌ INTEGRITY VIOLATION: Assignment #{assignment.id} → Activity #{assignment.resource_id}")
            all_valid = False

    if all_valid:
        print("✅ All assignments point to existing activities")
        print("✅ Referential integrity verified")
    else:
        print("⚠️  Integrity issues found - re-run cleanup")

    return all_valid


def main():
    """Main entry point."""
    print("Starting orphan assignments cleanup...")

    db = get_session()
    try:
        # Cleanup
        total, removed, remaining = cleanup_orphan_assignments(db)

        # Verify
        verify_integrity(db)

        # Summary
        print("\n" + "="*60)
        print("📊 CLEANUP SUMMARY")
        print("="*60)
        print(f"  Total checked:     {total}")
        print(f"  Orphans removed:   {removed}")
        print(f"  Valid remaining:   {remaining}")
        print("="*60)
        print("\n🎉 Cleanup complete!")

    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
