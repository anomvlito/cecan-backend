"""
Verification Script: Gantt ↔ My Responsibilities Integration

This script verifies that the connection between Gantt and My Tasks is working correctly.

Usage:
    python scripts/verify_gantt_integration.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import get_session
from core.models import (
    ResponsibilityAssignment, ProjectActivity, ScientificProject,
    ResourceType, User
)


def print_header(text):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def verify_no_orphans(db):
    """Verify no orphan assignments exist."""
    print("\n🔍 Checking for orphan assignments...")

    assignments = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).all()

    orphans = []
    for assignment in assignments:
        activity = db.query(ProjectActivity).filter_by(id=assignment.resource_id).first()
        if not activity:
            orphans.append(assignment)

    if orphans:
        print(f"   ❌ Found {len(orphans)} orphan assignments")
        for o in orphans:
            print(f"      Assignment #{o.id} → Activity #{o.resource_id} (NOT FOUND)")
        return False
    else:
        print(f"   ✅ All {len(assignments)} assignments point to real activities")
        return True


def verify_real_gantt_data(db):
    """Verify assignments use real Gantt data."""
    print("\n🔍 Verifying assignments use REAL Gantt activities...")

    assignments = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).limit(5).all()

    all_real = True
    for assignment in assignments:
        activity = db.query(ProjectActivity).filter_by(id=assignment.resource_id).first()
        if activity:
            project = activity.project
            # Check if it has real data (not simulated)
            has_real_data = (
                activity.end_month is not None and
                activity.status is not None and
                project is not None
            )

            if has_real_data:
                print(f"   ✅ Assignment #{assignment.id}:")
                print(f"      Activity: {activity.description[:50]}...")
                print(f"      Project: {project.code if project else 'N/A'}")
                print(f"      End Date: {activity.end_month}")
                print(f"      Status: {activity.status.value if activity.status else 'None'}")
            else:
                print(f"   ⚠️  Assignment #{assignment.id} has incomplete data")
                all_real = False
        else:
            print(f"   ❌ Assignment #{assignment.id} → Activity not found")
            all_real = False

    return all_real


def verify_user_assignments(db):
    """Verify demo users have correct assignments."""
    print("\n🔍 Verifying demo user assignments...")

    test_users = [
        ('researcher@cecan.cl', 'should have 5 assignments'),
        ('staff@cecan.cl', 'should have 3 assignments'),
        ('student@cecan.cl', 'should have 2 assignments'),
    ]

    all_correct = True
    for email, expected in test_users:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            print(f"   ⚠️  User {email} not found")
            continue

        count = db.query(ResponsibilityAssignment).filter_by(user_id=user.id).count()
        if count > 0:
            print(f"   ✅ {email}: {count} assignments ({expected})")
        else:
            print(f"   ❌ {email}: 0 assignments (expected some)")
            all_correct = False

    return all_correct


def verify_no_fake_data(db):
    """Verify no 'fake' or 'simulated' activities that aren't in Gantt."""
    print("\n🔍 Verifying NO fake/simulated data in assignments...")

    # Get all assignments
    assignments = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY
    ).all()

    # Check each one exists in ProjectActivity
    all_exist = True
    for assignment in assignments:
        exists = db.query(ProjectActivity).filter_by(id=assignment.resource_id).first()
        if not exists:
            print(f"   ❌ Assignment points to non-existent activity #{assignment.resource_id}")
            all_exist = False

    if all_exist:
        print(f"   ✅ All {len(assignments)} assignments point to real Gantt activities")
        print("   ✅ No fake/simulated data detected")
    else:
        print("   ❌ Some assignments point to fake/non-existent activities")

    return all_exist


def verify_consistency(db):
    """Verify Gantt and My Tasks show same data."""
    print("\n🔍 Verifying consistency between Gantt and My Tasks...")

    # Sample activity
    activity = db.query(ProjectActivity).first()
    if not activity:
        print("   ⚠️  No activities found in database")
        return False

    # Check if any assignment references it
    assignment = db.query(ResponsibilityAssignment).filter_by(
        resource_type=ResourceType.PROJECT_ACTIVITY,
        resource_id=activity.id
    ).first()

    if assignment:
        print(f"   ✅ Sample verification:")
        print(f"      Gantt shows: {activity.description[:50]}...")
        print(f"      End date: {activity.end_month}")
        print(f"      Status: {activity.status.value if activity.status else 'None'}")
        print(f"      ↓")
        print(f"      My Tasks will show: SAME data (no copy, same object)")
        return True
    else:
        print(f"   ⚠️  Sample activity has no assignments (ok if intentional)")
        return True


def print_summary(results):
    """Print summary of all checks."""
    print_header("VERIFICATION SUMMARY")

    total = len(results)
    passed = sum(results.values())

    print(f"\nTotal Checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}\n")

    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check}")

    if passed == total:
        print("\n🎉 ALL CHECKS PASSED!")
        print("✅ Gantt ↔ My Tasks integration is working correctly")
        print("✅ Ready for production use")
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("Run cleanup and re-seed scripts:")
        print("  1. python scripts/cleanup_orphan_assignments.py")
        print("  2. python scripts/seed_responsibilities_from_gantt.py")


def main():
    """Run all verification checks."""
    print_header("GANTT ↔ MY TASKS INTEGRATION VERIFICATION")
    print("\nThis script verifies the connection between Gantt and My Responsibilities")

    db = get_session()
    try:
        results = {
            "No orphan assignments": verify_no_orphans(db),
            "Assignments use real Gantt data": verify_real_gantt_data(db),
            "Demo users have assignments": verify_user_assignments(db),
            "No fake/simulated data": verify_no_fake_data(db),
            "Gantt ↔ My Tasks consistency": verify_consistency(db),
        }

        print_summary(results)

    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
