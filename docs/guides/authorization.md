# Authorization & Access Control Guide

This guide explains the CECAN Platform's authorization system, which combines **Role-Based Access Control (RBAC)** with the **RACI responsibility model** for fine-grained resource permissions.

## Table of Contents

- [Overview](#overview)
- [User Roles (RBAC)](#user-roles-rbac)
- [RACI Responsibility Model](#raci-responsibility-model)
- [Authorization Logic](#authorization-logic)
- [API Endpoints](#api-endpoints)
- [Frontend Integration](#frontend-integration)
- [Demo Users](#demo-users)
- [Testing Scenarios](#testing-scenarios)
- [Troubleshooting](#troubleshooting)

---

## Overview

The CECAN authorization system provides two layers of access control:

1. **Platform Roles (RBAC)**: User-level roles that grant broad platform permissions
2. **Resource Responsibilities (RACI)**: Project/resource-specific assignments defining who is Responsible, Accountable, Consulted, or Informed

This dual approach allows for:
- **Platform-wide permissions** (e.g., admins can manage all data)
- **Organizational flexibility** (e.g., a PI can be Accountable for Project A but only Consulted on Project B)
- **Work Package scoping** (users see data from their assigned Work Packages)

---

## User Roles (RBAC)

### Available Roles

| Role | Enum Value | Description | Typical Permissions |
|------|-----------|-------------|---------------------|
| **Super Admin** | `super_admin` | Platform owner | Full system access, user management, configuration |
| **Admin** | `admin` | Administrative staff | Manage researchers, projects, publications across all WPs |
| **Staff** | `staff` | Support personnel | Create/edit data, limited administrative functions |
| **PI** | `pi` | Principal Investigator | Manage own projects, team members, publications within WP |
| **Researcher** | `researcher` | Research team member | Contribute to assigned projects, manage own publications |
| **Student** | `student` | Student researcher | View assigned projects, limited editing |
| **Editor** | `editor` | Content editor | Edit publications and metadata |
| **Viewer** | `viewer` | Read-only observer | View dashboard only, no data modification |

### Role Hierarchy

```
super_admin (full access)
  ├── admin (cross-WP management)
  ├── staff (operational tasks)
  ├── pi (WP project ownership)
  ├── researcher (contribution)
  ├── student (limited contribution)
  ├── editor (content editing)
  └── viewer (read-only)
```

### Database Schema

Roles are stored as an enum in PostgreSQL:

```sql
CREATE TYPE userrole AS ENUM (
    'super_admin',
    'admin',
    'staff',
    'pi',
    'researcher',
    'student',
    'editor',
    'viewer'
);
```

**Important**: The enum uses **lowercase strings** (`'pi'`, not `'PI'`). The Python `UserRole` enum maps to these values:

```python
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    STAFF = "staff"
    PI = "pi"
    RESEARCHER = "researcher"
    STUDENT = "student"
    EDITOR = "editor"
    VIEWER = "viewer"
```

---

## RACI Responsibility Model

RACI defines four types of responsibility for resources (projects, publications, activities):

### RACI Roles

| Role | Description | Permissions | Example |
|------|-------------|-------------|---------|
| **R** - Responsible | Does the work | Create, edit, contribute | Researcher assigned to execute tasks |
| **A** - Accountable | Ultimate owner, decision maker | Full control (update, delete) | PI who owns the project |
| **C** - Consulted | Provides input | View, comment (read-only) | External advisor |
| **I** - Informed | Kept up-to-date | View only (read-only) | Stakeholders, administrators |

### Resource Types

The RACI model applies to:

```python
class ResourceType(str, Enum):
    SCIENTIFIC_PROJECT = "scientific_project"
    PROJECT_ACTIVITY = "project_activity"
    PUBLICATION = "publication"
    WORK_PACKAGE = "work_package"
```

### Database Schema

Responsibility assignments are stored in the `responsibility_assignments` table:

```sql
CREATE TABLE responsibility_assignments (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES academic_members(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    resource_type VARCHAR(50) NOT NULL,  -- 'scientific_project', 'publication', etc.
    resource_id INTEGER NOT NULL,
    raci_role VARCHAR(1) NOT NULL,  -- 'R', 'A', 'C', 'I'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_member_resource_role UNIQUE (member_id, resource_type, resource_id, raci_role)
);
```

**Key Indexes**:
- `idx_resp_resource`: `(resource_type, resource_id)` for fast resource lookups
- `idx_resp_member`: `(member_id)` for user-specific queries
- Unique constraint prevents duplicate assignments

---

## Authorization Logic

### The `can()` Function

The core authorization engine is `services/authz.py::can()`:

```python
def can(user: User, action: str, resource, responsibilities: List[ResponsibilityAssignment] = None) -> bool:
    """
    Check if user can perform action on resource.

    Args:
        user: The authenticated User object
        action: Action verb ('view', 'update', 'delete', 'create')
        resource: The resource object being accessed (ScientificProject, Publication, etc.)
        responsibilities: Pre-loaded RACI assignments for the resource (optional)

    Returns:
        True if authorized, False otherwise
    """
```

### Authorization Rules

The function applies rules in this order:

1. **Super Admin Override**: `super_admin` role always returns `True`

2. **Resource Ownership**:
   - If resource has `.created_by_id` matching `user.id` → `True` for all actions
   - If resource is a `ScientificProject` and user role is `pi` with matching WP → `True`

3. **RACI Assignments**:
   - If user has **Accountable (A)** or **Responsible (R)** role → `True` for `update`/`delete`
   - If user has **any RACI role** (R/A/C/I) → `True` for `view`

4. **Work Package Scope**:
   - If resource has `.wp_id` matching user's member WP → `True` for `view`
   - Allows WP-level visibility across team members

5. **Platform Roles**:
   - `admin`, `staff` → `True` for all actions
   - `editor` → `True` for `view` and `update` on publications
   - `viewer` → `True` only for `view` on dashboard

### Example Usage in API Routes

```python
from services.authz import can
from database.repositories.responsibility_repository import get_responsibilities_for_resource

@router.put("/scientific-projects/{project_id}")
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Load the resource
    project = db.query(ScientificProject).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load RACI assignments
    responsibilities = get_responsibilities_for_resource(
        db,
        ResourceType.SCIENTIFIC_PROJECT.value,
        project_id
    )

    # Check authorization
    if not can(current_user, "update", project, responsibilities):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this project"
        )

    # Proceed with update...
```

---

## API Endpoints

### Responsibilities CRUD

**Base Path**: `/api/responsibilities`

#### Create Responsibility Assignment

```http
POST /api/responsibilities
Authorization: Bearer <token>
Content-Type: application/json

{
  "member_id": 42,
  "resource_type": "scientific_project",
  "resource_id": 10,
  "raci_role": "A"
}
```

**Response** (201):
```json
{
  "id": 5,
  "member_id": 42,
  "user_id": null,
  "resource_type": "scientific_project",
  "resource_id": 10,
  "raci_role": "A",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Authorization**: Only users with permission to manage the resource can create assignments.

---

#### List All Responsibilities

```http
GET /api/responsibilities?resource_type=scientific_project&resource_id=10
Authorization: Bearer <token>
```

**Query Parameters**:
- `resource_type` (optional): Filter by resource type
- `resource_id` (optional): Filter by resource ID

**Response** (200):
```json
[
  {
    "id": 5,
    "member_id": 42,
    "user_id": 15,
    "resource_type": "scientific_project",
    "resource_id": 10,
    "raci_role": "A",
    "created_at": "2025-01-15T10:30:00Z",
    "member": {
      "id": 42,
      "full_name": "Dr. Jane Smith",
      "email": "jane@cecan.cl"
    }
  }
]
```

---

#### Get My Responsibilities

```http
GET /api/responsibilities/my
Authorization: Bearer <token>
```

**Response** (200): Returns all RACI assignments for the authenticated user's member record.

---

#### Delete Responsibility Assignment

```http
DELETE /api/responsibilities/{responsibility_id}
Authorization: Bearer <token>
```

**Response** (200):
```json
{
  "message": "Responsibility deleted successfully"
}
```

**Authorization**: Only users who can manage the resource can delete assignments.

---

### Protected Endpoints

The following endpoints now enforce authorization:

#### Scientific Projects

- `GET /api/scientific-projects` - Filters by user's WP scope
- `POST /api/scientific-projects` - Requires `create` permission
- `PUT /api/scientific-projects/{id}` - Requires `update` permission (ownership or RACI A/R)
- `DELETE /api/scientific-projects/{id}` - Requires `delete` permission (ownership or RACI A)

#### Publications

- `GET /api/publications` - Filters by user's WP scope
- `PUT /api/publications/{id}` - Requires `update` permission
- `DELETE /api/publications/{id}` - Requires `delete` permission

---

## Frontend Integration

### Enhanced `/api/me` Endpoint

The `/api/me` endpoint now returns rich user context:

```http
GET /api/auth/me
Authorization: Bearer <token>
```

**Response**:
```json
{
  "user": {
    "id": 15,
    "email": "pi@cecan.cl",
    "full_name": "Dr. Gregory House",
    "role": "pi",
    "is_active": true,
    "created_at": "2025-01-10T08:00:00Z"
  },
  "academic_member": {
    "id": 42,
    "full_name": "Dr. Gregory House",
    "email": "pi@cecan.cl",
    "member_type": "researcher",
    "wp_id": 1,
    "institution": "Hospital Princeton",
    "researcher_details": {
      "category": "Principal",
      "is_auditable": true
    },
    "work_packages": [
      {
        "id": 1,
        "name": "WP1 - Prevention & Reduction"
      }
    ]
  }
}
```

**Key Fields**:
- `user.role`: Platform role (enum value as string)
- `academic_member`: Organizational identity (null if user is not linked to a member)
- `academic_member.wp_id`: Primary Work Package assignment
- `researcher_details`: Additional metadata for researchers (category, auditability)
- `work_packages`: List of all WP assignments

---

### AuthContext API (React)

**Location**: `cecan-frontend/src/context/AuthContext.tsx`

#### State

```typescript
const {
  user,           // User account info (id, email, role)
  member,         // Academic member context (or null)
  isAuthenticated,
  isLoading
} = useAuth();
```

#### Helper Functions

```typescript
// Check if user has any of the specified roles
hasRole(['admin', 'staff']): boolean

// Check if user is an admin (super_admin, admin, or staff)
isAdmin(): boolean
```

**Example Usage**:
```typescript
import { useAuth } from '@/context/AuthContext';

function MyComponent() {
  const { user, member, hasRole, isAdmin } = useAuth();

  return (
    <div>
      <h1>Welcome, {member?.full_name || user?.full_name}!</h1>
      <p>Role: {user?.role}</p>

      {hasRole(['admin', 'staff']) && (
        <button>Admin Action</button>
      )}

      {isAdmin() && (
        <Link to="/admin/data-studio">Data Studio</Link>
      )}
    </div>
  );
}
```

---

### Protected Routes

**Location**: `cecan-frontend/src/components/layout/ProtectedRoute.tsx`

#### Basic Protection

```typescript
// Require authentication only
<Route element={<ProtectedRoute />}>
  <Route path="/dashboard" element={<Dashboard />} />
</Route>
```

#### Role-Based Protection

```typescript
// Require specific roles
<Route element={<ProtectedRoute requiredRoles={['admin', 'super_admin', 'staff']} />}>
  <Route path="/admin/data-studio" element={<DataStudio />} />
</Route>

// Multiple role options
<Route element={<ProtectedRoute requiredRoles={['pi', 'researcher']} />}>
  <Route path="/scientific-projects/create" element={<CreateProject />} />
</Route>
```

**Behavior**:
- Redirects to `/login` if not authenticated
- Redirects to `/dashboard` if authenticated but lacks required role
- Shows loading spinner while authentication state is loading

---

### Dynamic Sidebar

**Location**: `cecan-frontend/src/components/layout/Sidebar.tsx`

The sidebar menu filters items based on user role:

```typescript
const visibleNavigation = navigation.filter((item) => {
  // Dashboard is visible to everyone
  if (item.name === "Dashboard") return true;

  // VIEWER role can only see Dashboard
  if (user?.role === 'viewer') return false;

  // All other authenticated users see all menu items
  return true;
});
```

**Admin Section**:
- Only shown if `isAdmin()` or `hasRole(['super_admin', 'admin', 'staff'])`
- Contains "Data Studio" and other administrative tools

---

## Demo Users

The platform includes pre-seeded demo users for testing:

| Email | Password | Role | Work Package | Description |
|-------|----------|------|--------------|-------------|
| `pi@cecan.cl` | `pi123` | `pi` | WP1 | Principal Investigator |
| `researcher@cecan.cl` | `res123` | `researcher` | WP1 | Associate Researcher |
| `student@cecan.cl` | `stu123` | `student` | WP1 | Student |
| `staff@cecan.cl` | `staff123` | `staff` | WP1 | Staff Member |
| `viewer@cecan.cl` | `view123` | `viewer` | WP1 | Read-only Observer |
| `admin@cecan.cl` | `admin123` | `admin` | WP1 | Administrator |

### Creating Demo Users

```bash
cd cecan-backend
.venv/bin/python scripts/seed_users_demo.py
```

**Note**: Each user is linked to an `AcademicMember` record with matching email.

---

## Testing Scenarios

### Scenario 1: PI Project Management

**User**: `pi@cecan.cl` (role: `pi`, WP1)

1. Login → Should see full sidebar menu
2. Navigate to **Scientific Projects** → Should see all WP1 projects
3. Create new project → Success (PI can create in their WP)
4. Edit own project → Success (ownership)
5. Delete own project → Success (ownership)

---

### Scenario 2: Researcher Collaboration

**Setup**:
- **User A**: `pi@cecan.cl` creates Project X
- **User B**: `researcher@cecan.cl` assigned as **Responsible (R)** on Project X

**Test Flow**:
1. User B logs in → Sees Project X in project list (RACI R grants visibility)
2. User B edits Project X → Success (RACI R allows update)
3. User B tries to delete Project X → **Denied** (only Accountable or owner can delete)

**Create RACI Assignment** (as PI):
```bash
curl -X POST http://localhost:8000/api/responsibilities \
  -H "Authorization: Bearer <pi_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": 43,  # researcher member_id
    "resource_type": "scientific_project",
    "resource_id": 10,
    "raci_role": "R"
  }'
```

---

### Scenario 3: Viewer Read-Only Access

**User**: `viewer@cecan.cl` (role: `viewer`)

1. Login → Sees **only Dashboard** in sidebar
2. Direct URL access to `/researchers` → Redirected to `/dashboard`
3. API calls to protected endpoints → 403 Forbidden
4. Dashboard shows aggregated metrics → Success (read-only data)

---

### Scenario 4: Admin Cross-WP Access

**User**: `admin@cecan.cl` (role: `admin`)

1. Login → Sees full menu + Admin section
2. Navigate to **Scientific Projects** → Sees projects from **all Work Packages**
3. Edit any project → Success (admin override)
4. Delete any project → Success (admin override)
5. Access **Data Studio** → Success (admin-only feature)

---

### Scenario 5: Student Limited Access

**User**: `student@cecan.cl` (role: `student`, WP1)

1. Login → Sees full sidebar (student can view)
2. Navigate to **Publications** → Sees WP1 publications
3. Try to create publication → **Check backend logic** (may need RACI assignment)
4. Try to edit unassigned publication → **Denied** (no ownership or RACI)

---

## Troubleshooting

### Issue: "Invalid input value for enum userrole"

**Error Message**:
```
psycopg2.errors.InvalidTextRepresentation: invalid input value for enum userrole: "PI"
```

**Cause**: SQLAlchemy using enum **name** (`PI`) instead of **value** (`"pi"`).

**Fix**: Ensure `User.role` column uses `values_callable`:

```python
# core/models.py
role = Column(
    SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
    nullable=False,
    default=UserRole.VIEWER
)
```

**Migration**: If enum has duplicate values, run cleanup:

```bash
psql -d cecan_db -f scripts/cleanup_enum_duplicates.sql
```

---

### Issue: User Has No Academic Member

**Symptom**: `academic_member` is `null` in `/api/me` response.

**Cause**: User account not linked to `AcademicMember` record (no matching email).

**Solution**:
1. Create `AcademicMember` with matching email:
   ```python
   member = AcademicMember(
       full_name="John Doe",
       email="user@cecan.cl",
       member_type="researcher",
       wp_id=1
   )
   db.add(member)
   db.commit()
   ```
2. User will automatically link on next login

---

### Issue: 403 Forbidden on Protected Endpoint

**Symptom**: API returns `{"detail": "You do not have permission to update this resource"}`

**Debugging Steps**:

1. **Check User Role**:
   ```bash
   curl http://localhost:8000/api/auth/me -H "Authorization: Bearer <token>"
   ```
   Verify `user.role` is expected value.

2. **Check RACI Assignments**:
   ```bash
   curl http://localhost:8000/api/responsibilities?resource_type=scientific_project&resource_id=10 \
     -H "Authorization: Bearer <token>"
   ```
   Verify user has **R** or **A** assignment.

3. **Check Resource Ownership**:
   Query database to see if `resource.created_by_id == user.id`

4. **Check Work Package Scope**:
   Verify `user.member.wp_id == resource.wp_id`

5. **Backend Logs**:
   Enable debug logging in `services/authz.py`:
   ```python
   logger.debug(f"can() check: user={user.email}, action={action}, role={user.role}")
   ```

---

### Issue: Sidebar Not Showing Admin Section

**Symptom**: User with `admin` role doesn't see "Data Studio" link.

**Cause**: `isAdmin()` check failing or user not properly authenticated.

**Solution**:
1. Check browser console for auth errors
2. Verify token is valid: decode JWT and check `sub` claim
3. Clear localStorage and re-login:
   ```javascript
   localStorage.removeItem('token');
   window.location.href = '/login';
   ```

---

### Issue: RACI Assignment Creation Fails

**Symptom**: POST `/api/responsibilities` returns 403 or 404.

**Common Causes**:

1. **Invalid `member_id`**: Member doesn't exist
   ```sql
   SELECT * FROM academic_members WHERE id = 42;
   ```

2. **Invalid `resource_id`**: Resource doesn't exist
   ```sql
   SELECT * FROM scientific_projects WHERE id = 10;
   ```

3. **Permission Denied**: Current user can't manage the resource
   - Verify user is owner, has admin role, or has RACI A/R on resource

4. **Duplicate Assignment**: Same member/resource/role combo exists
   - Check unique constraint: `(member_id, resource_type, resource_id, raci_role)`

---

## Best Practices

### 1. Always Pre-Load RACI Assignments

When checking permissions on a specific resource, load RACI assignments **once** and pass to `can()`:

```python
# ✅ GOOD: Load once, reuse
responsibilities = get_responsibilities_for_resource(db, resource_type, resource_id)
if not can(user, "update", project, responsibilities):
    raise HTTPException(403)
# ... later in same function
if not can(user, "delete", project, responsibilities):  # Reuses same list
    raise HTTPException(403)

# ❌ BAD: Repeated database queries
if not can(user, "update", project):  # Would need to query DB internally
    raise HTTPException(403)
```

### 2. Use Specific Error Messages

Differentiate between "not found" and "forbidden":

```python
project = db.query(ScientificProject).filter_by(id=project_id).first()
if not project:
    raise HTTPException(status_code=404, detail="Project not found")  # Resource doesn't exist

if not can(user, "update", project):
    raise HTTPException(status_code=403, detail="You do not have permission to update this project")  # Exists but no access
```

### 3. Assign RACI Roles When Creating Resources

When a user creates a project, automatically assign them as **Accountable**:

```python
@router.post("/scientific-projects")
async def create_project(data: ProjectCreate, current_user: User, db: Session):
    # Create project
    project = ScientificProject(**data.dict(), created_by_id=current_user.id)
    db.add(project)
    db.flush()

    # Auto-assign creator as Accountable
    if current_user.member_id:
        assignment = ResponsibilityAssignment(
            member_id=current_user.member_id,
            resource_type=ResourceType.SCIENTIFIC_PROJECT.value,
            resource_id=project.id,
            raci_role="A"
        )
        db.add(assignment)

    db.commit()
    return project
```

### 4. Frontend: Check Permissions Before Showing UI

Hide/disable actions the user can't perform:

```typescript
function ProjectCard({ project }) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(['admin', 'staff', 'pi', 'researcher']);

  return (
    <div>
      <h3>{project.title}</h3>
      {canEdit && (
        <button onClick={() => editProject(project.id)}>Edit</button>
      )}
    </div>
  );
}
```

**Note**: Always enforce authorization on the **backend**. Frontend checks are for UX only.

---

## Related Documentation

- **CLAUDE.md**: Quick reference for authorization system
- **docs/architecture/backend.md**: Backend architecture overview
- **docs/guides/scientific_projects.md**: Scientific projects module guide
- **API Documentation**: http://localhost:8000/docs (Swagger UI)

---

## Changelog

- **2025-01-15**: Initial authorization system implementation (Phases 1-3)
  - User roles enum extended
  - RACI responsibility model
  - `services/authz.py` authorization engine
  - Protected endpoints for projects and publications
  - Enhanced `/api/me` endpoint
  - Frontend role-based access control
