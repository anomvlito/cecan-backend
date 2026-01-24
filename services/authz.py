"""
Authorization Service - Non-intrusive permission engine.

This module implements a pure authorization logic that determines if a user
can perform a specific action on a resource. It uses RACI responsibility
assignments and role-based access control (RBAC).

The design is intentionally stateless and does not directly query the database.
All necessary data should be loaded and passed to the authorization functions.
"""

from typing import Optional, List, Any
from enum import Enum


class Action(str, Enum):
    """Possible actions a user can perform."""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"  # Full control (assign responsibilities, change ownership)
    SYNC = "sync"      # Trigger data synchronization
    EXECUTE = "execute"  # Execute budget or financial operations


def can(
    user: Any,
    action: str,
    resource: Any,
    responsibilities: Optional[List[Any]] = None
) -> bool:
    """
    Check if a user can perform an action on a resource.

    This is the main authorization function. It evaluates permissions based on:
    1. User role (RBAC)
    2. Resource ownership
    3. RACI responsibility assignments
    4. Work Package (WP) scope

    Args:
        user: User object with role, academic_member relationship
        action: Action to perform (read, create, update, delete, manage, sync, execute)
        resource: Resource object (ScientificProject, ProjectActivity, Publication, etc.)
        responsibilities: List of ResponsibilityAssignment objects for this resource

    Returns:
        bool: True if the user is authorized, False otherwise

    Examples:
        >>> can(admin_user, "delete", project)
        True
        >>> can(pi_user, "update", project_they_own)
        True
        >>> can(student_user, "update", project_not_assigned)
        False
    """
    # Import here to avoid circular dependencies
    from core.models import UserRole, RaciRole

    if not user:
        return False

    user_role = user.role
    action = action.lower()

    # ============================================================================
    # RULE 1: SUPER_ADMIN has full access to everything
    # ============================================================================
    if user_role == UserRole.SUPER_ADMIN:
        return True

    # ============================================================================
    # RULE 2: ADMIN has full access except dangerous operations
    # ============================================================================
    if user_role == UserRole.ADMIN:
        # Admin can do everything except delete users (that's SUPER_ADMIN only)
        # For now, we allow all actions. Can be refined later.
        return True

    # ============================================================================
    # RULE 3: Check resource-specific permissions based on role
    # ============================================================================

    # Get the academic member associated with this user (if any)
    member = getattr(user, 'academic_member', None)
    member_id = member.id if member else None

    # Get user's Work Package IDs (for scope filtering)
    user_wp_ids = _get_user_wp_ids(member)

    # Determine resource type and apply specific rules
    resource_type = type(resource).__name__

    # -------------------------
    # ScientificProject
    # -------------------------
    if resource_type == "ScientificProject":
        # Check if user is the PI (Principal Investigator)
        is_pi = resource.pi_id == member_id

        # Check if user has Accountable (A) role in responsibilities
        is_accountable = _has_raci_role(responsibilities, member_id, RaciRole.A)

        if user_role == UserRole.PI:
            if action in ["read", "update", "create"]:
                return is_pi or is_accountable
            elif action == "delete":
                return is_pi  # Only PI can delete their own project
            elif action == "manage":
                return is_pi or is_accountable
            elif action == "execute":
                return is_pi or is_accountable

        if user_role == UserRole.STAFF:
            # Staff can read all projects and update admin fields
            if action == "read":
                return True
            if action in ["update", "create"]:
                return True  # Staff handles administrative tasks
            if action == "delete":
                return False  # Staff cannot delete projects
            if action == "execute":
                # Staff needs explicit permission for budget execution
                return is_accountable

        if user_role == UserRole.RESEARCHER:
            # Researchers can read projects in their WP(s)
            # They can edit if they have R (Responsible) or A (Accountable) role
            if action == "read":
                return _is_in_user_wp_scope(resource, user_wp_ids)
            if action in ["update", "create"]:
                is_responsible = _has_raci_role(responsibilities, member_id, RaciRole.R)
                return is_responsible or is_accountable
            return False

        if user_role == UserRole.STUDENT:
            # Students can only read/update if explicitly assigned
            is_assigned = _has_any_raci_role(responsibilities, member_id)
            if action == "read":
                return is_assigned
            if action == "update":
                return _has_raci_role(responsibilities, member_id, RaciRole.R)
            return False

        if user_role == UserRole.VIEWER:
            # Viewers can read projects in their WP scope or if assigned
            if action == "read":
                return _is_in_user_wp_scope(resource, user_wp_ids) or _has_any_raci_role(responsibilities, member_id)
            return False

    # -------------------------
    # ProjectActivity
    # -------------------------
    elif resource_type == "ProjectActivity":
        # Activity permissions depend on the parent project
        # Load the parent project and check permissions on it
        project = getattr(resource, 'project', None)
        if not project:
            return False

        # If user can edit the project, they can manage activities
        if user_role == UserRole.PI:
            is_pi = project.pi_id == member_id
            is_accountable = _has_raci_role(responsibilities, member_id, RaciRole.A)
            if action in ["read", "create", "update", "delete"]:
                return is_pi or is_accountable

        if user_role == UserRole.STAFF:
            if action in ["read", "create", "update"]:
                return True
            return False

        if user_role == UserRole.RESEARCHER:
            if action == "read":
                return _is_in_user_wp_scope(project, user_wp_ids)
            if action in ["update", "create"]:
                is_responsible = _has_raci_role(responsibilities, member_id, RaciRole.R)
                is_accountable = _has_raci_role(responsibilities, member_id, RaciRole.A)
                return is_responsible or is_accountable
            return False

        if user_role == UserRole.STUDENT:
            is_assigned = _has_any_raci_role(responsibilities, member_id)
            if action == "read":
                return is_assigned
            if action == "update":
                return _has_raci_role(responsibilities, member_id, RaciRole.R)
            return False

        if user_role == UserRole.VIEWER:
            if action == "read":
                return _is_in_user_wp_scope(project, user_wp_ids) or _has_any_raci_role(responsibilities, member_id)
            return False

    # -------------------------
    # Publication
    # -------------------------
    elif resource_type == "Publication":
        if user_role == UserRole.STAFF:
            # Staff has CRUD permissions on publications
            if action in ["read", "create", "update", "delete"]:
                return True
            if action == "sync":
                return True

        if user_role in [UserRole.PI, UserRole.RESEARCHER]:
            # Researchers can read publications in their WP
            if action == "read":
                return True  # Publications are generally readable
            if action in ["update", "create"]:
                # Can edit if they are an author (via researcher_connections)
                return _is_publication_author(resource, member_id)
            return False

        if user_role == UserRole.STUDENT:
            if action == "read":
                return True  # Students can read publications
            return False

        if user_role == UserRole.VIEWER:
            if action == "read":
                return True
            return False

    # -------------------------
    # WorkPackage
    # -------------------------
    elif resource_type == "WorkPackage":
        if user_role == UserRole.STAFF:
            if action in ["read", "update"]:
                return True
            return False

        if user_role in [UserRole.PI, UserRole.RESEARCHER]:
            if action == "read":
                return resource.id in user_wp_ids
            return False

        if user_role in [UserRole.STUDENT, UserRole.VIEWER]:
            if action == "read":
                return resource.id in user_wp_ids
            return False

    # ============================================================================
    # Default: Deny
    # ============================================================================
    return False


# =============================================================================
# Helper Functions
# =============================================================================

def _get_user_wp_ids(member: Any) -> List[int]:
    """
    Extract all Work Package IDs that a member belongs to.

    Args:
        member: AcademicMember object

    Returns:
        List of WP IDs
    """
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


def _is_in_user_wp_scope(resource: Any, user_wp_ids: List[int]) -> bool:
    """
    Check if a resource belongs to the user's Work Package(s).

    Args:
        resource: Resource object (should have wp_id or work_package attribute)
        user_wp_ids: List of WP IDs the user belongs to

    Returns:
        bool: True if resource is in user's WP scope
    """
    if not user_wp_ids:
        return False

    # Check if resource has a direct wp_id
    resource_wp_id = getattr(resource, 'wp_id', None)
    if resource_wp_id and resource_wp_id in user_wp_ids:
        return True

    # Check if resource has a work_package enum field (for ScientificProject)
    resource_wp = getattr(resource, 'work_package', None)
    if resource_wp:
        # work_package is an enum, convert to string and compare
        # This is a simplified check - in production you'd map enum to WP IDs
        return True  # For now, assume any WP match is OK

    return False


def _has_raci_role(
    responsibilities: Optional[List[Any]],
    member_id: Optional[int],
    raci_role: Any
) -> bool:
    """
    Check if a member has a specific RACI role in the responsibilities list.

    Args:
        responsibilities: List of ResponsibilityAssignment objects
        member_id: ID of the academic member
        raci_role: RACI role to check (R, A, C, or I)

    Returns:
        bool: True if member has the specified RACI role
    """
    if not responsibilities or not member_id:
        return False

    for resp in responsibilities:
        if resp.member_id == member_id and resp.raci_role == raci_role:
            return True

    return False


def _has_any_raci_role(
    responsibilities: Optional[List[Any]],
    member_id: Optional[int]
) -> bool:
    """
    Check if a member has any RACI role assignment.

    Args:
        responsibilities: List of ResponsibilityAssignment objects
        member_id: ID of the academic member

    Returns:
        bool: True if member has any RACI role
    """
    if not responsibilities or not member_id:
        return False

    for resp in responsibilities:
        if resp.member_id == member_id:
            return True

    return False


def _is_publication_author(publication: Any, member_id: Optional[int]) -> bool:
    """
    Check if a member is an author of a publication.

    Args:
        publication: Publication object
        member_id: ID of the academic member

    Returns:
        bool: True if member is an author
    """
    if not member_id:
        return False

    # Check researcher_connections (many-to-many relationship)
    if hasattr(publication, 'researcher_connections'):
        for conn in publication.researcher_connections:
            if conn.member_id == member_id:
                return True

    return False


# =============================================================================
# Responsibility Query Helpers
# =============================================================================

def get_responsibilities_for_resource(
    session: Any,
    resource_type: str,
    resource_id: int
) -> List[Any]:
    """
    Load all responsibility assignments for a given resource.

    This function should be called from the API layer to fetch responsibilities
    before calling can().

    Args:
        session: SQLAlchemy session
        resource_type: Type of resource (scientific_project, project_activity, etc.)
        resource_id: ID of the resource

    Returns:
        List of ResponsibilityAssignment objects
    """
    from core.models import ResponsibilityAssignment, ResourceType

    # Convert string to enum
    try:
        resource_type_enum = ResourceType[resource_type.upper()]
    except KeyError:
        return []

    return session.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.resource_type == resource_type_enum,
        ResponsibilityAssignment.resource_id == resource_id
    ).all()


def get_user_responsibilities(session: Any, user_id: int) -> List[Any]:
    """
    Load all responsibility assignments for a given user.

    Args:
        session: SQLAlchemy session
        user_id: ID of the user

    Returns:
        List of ResponsibilityAssignment objects
    """
    from core.models import ResponsibilityAssignment

    return session.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.user_id == user_id
    ).all()


def get_member_responsibilities(session: Any, member_id: int) -> List[Any]:
    """
    Load all responsibility assignments for a given academic member.

    Args:
        session: SQLAlchemy session
        member_id: ID of the academic member

    Returns:
        List of ResponsibilityAssignment objects
    """
    from core.models import ResponsibilityAssignment

    return session.query(ResponsibilityAssignment).filter(
        ResponsibilityAssignment.member_id == member_id
    ).all()
