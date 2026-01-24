# Backend Architecture

This document describes the architecture and key components of the CECAN Platform backend.

## Tech Stack

- **Framework**: FastAPI 0.128.0
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL 13+
- **Authentication**: JWT (JSON Web Tokens)
- **Python Version**: 3.11+

## Project Structure

```
cecan-backend/
├── main.py                 # Application entry point, FastAPI app initialization
├── config.py              # Configuration management (env variables, settings)
├── database/              # Database session management and repositories
│   ├── session.py         # SQLAlchemy session factory
│   └── repositories/      # Data access layer
├── core/                  # Core domain models
│   └── models.py          # SQLAlchemy ORM models
├── schemas.py             # Pydantic validation schemas
├── services/              # Business logic layer
│   ├── auth_service.py    # Authentication operations
│   ├── authz.py           # Authorization logic (RBAC + RACI)
│   └── ...
├── api/                   # REST API layer
│   └── routes/            # API route modules
│       ├── auth.py        # Authentication endpoints
│       ├── publications.py
│       ├── scientific_projects.py
│       ├── responsibilities.py  # RACI management
│       └── ...
├── utils/                 # Utilities and helpers
│   ├── security.py        # Password hashing, JWT creation
│   └── ...
├── alembic/               # Database migrations
│   └── versions/          # Migration scripts
└── scripts/               # Utility scripts
    ├── seed_users_demo.py
    └── ...
```

## Key Components

### 1. Application Entry Point (`main.py`)

Initializes the FastAPI application, configures CORS, includes routers, and defines global middleware.

```python
app = FastAPI(title="CECAN Platform API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(projects_router, prefix="/api/scientific-projects", tags=["projects"])
# ...
```

### 2. Database Layer

**Session Management** (`database/session.py`):
- Provides `get_db()` dependency for route injection
- Manages connection pooling and transaction lifecycle

**Repositories** (`database/repositories/`):
- Encapsulate data access logic
- Example: `responsibility_repository.py` handles RACI assignment queries

### 3. Core Models (`core/models.py`)

SQLAlchemy ORM models representing database tables:

- `User`: Authentication accounts
- `AcademicMember`: Organizational identity (researchers, students, staff)
- `UserRole`: Enum defining platform roles
- `ScientificProject`: Research projects
- `Publication`: Scientific papers
- `Journal`: Journal metadata with impact metrics
- `WorkPackage`: Organizational units
- `ResponsibilityAssignment`: RACI role assignments
- `RaciRole`: Enum (R, A, C, I)
- `ResourceType`: Enum (scientific_project, publication, etc.)

**Key Relationships**:
- `User.member_id` → `AcademicMember.id` (1-to-1 via email matching)
- `AcademicMember.wp_id` → `WorkPackage.id`
- `ResponsibilityAssignment.member_id` → `AcademicMember.id`
- `Publication.journal_id` → `Journal.id`

### 4. Schemas (`schemas.py`)

Pydantic models for request validation and response serialization:

- `UserCreate`, `UserRead`: User management
- `ProjectCreate`, `ProjectUpdate`, `ProjectRead`: Scientific projects
- `PublicationCreate`, `PublicationRead`: Publications
- `ResponsibilityCreate`, `ResponsibilityRead`: RACI assignments
- `UserMeResponse`: Enhanced user context for `/api/me`

### 5. Services Layer

**Authentication (`services/auth_service.py`)**:
- `authenticate_user()`: Validate email/password
- `create_user()`: User registration with role handling
- `generate_token()`: Create JWT access tokens
- `get_user_by_email()`: User lookup

**Authorization (`services/authz.py`)**:
- `can(user, action, resource, responsibilities)`: Core permission check
- Implements RBAC (role-based) + RACI (responsibility-based) logic
- See [Authorization Guide](../guides/authorization.md) for details

### 6. API Routes (`api/routes/`)

RESTful endpoints organized by domain:

**Authentication (`auth.py`)**:
- `POST /api/auth/login`: Login with email/password, returns JWT
- `GET /api/auth/me`: Get current user + academic member context
- `POST /api/auth/register`: Create new user account

**Scientific Projects (`scientific_projects.py`)**:
- `GET /api/scientific-projects`: List projects (filtered by WP scope)
- `POST /api/scientific-projects`: Create project (requires permission)
- `PUT /api/scientific-projects/{id}`: Update project (authorization enforced)
- `DELETE /api/scientific-projects/{id}`: Delete project (authorization enforced)

**Publications (`publications.py`)**:
- `GET /api/publications`: List publications (filtered by WP scope)
- `POST /api/publications`: Create publication
- `PUT /api/publications/{id}`: Update publication (authorization enforced)
- `DELETE /api/publications/{id}`: Delete publication (authorization enforced)

**Responsibilities (`responsibilities.py`)**:
- `POST /api/responsibilities`: Assign RACI role to member for resource
- `GET /api/responsibilities`: List all assignments (with filters)
- `GET /api/responsibilities/my`: Get current user's assignments
- `DELETE /api/responsibilities/{id}`: Remove assignment

**Other Routes**:
- `enrichment.py`: AI-powered metadata enrichment pipeline
- `rag.py`: RAG chat with FAISS vector store
- `external.py`: OpenAlex API integration
- `cross_validation.py`: Data quality validation
- `collaboration_matrix.py`: Co-authorship analysis

### 7. Utilities (`utils/`)

**Security (`utils/security.py`)**:
- `get_password_hash()`: Hash passwords using bcrypt
- `verify_password()`: Validate password against hash
- `create_access_token()`: Generate JWT with expiration
- `decode_access_token()`: Validate and decode JWT
- `get_current_user()`: FastAPI dependency for auth

## Authorization System

CECAN implements a dual-layer authorization model:

### Platform Roles (RBAC)

Users are assigned one of eight platform roles that define broad permissions:

| Role | Value | Description |
|------|-------|-------------|
| Super Admin | `super_admin` | Full platform access |
| Admin | `admin` | Cross-WP management |
| Staff | `staff` | Operational tasks |
| PI | `pi` | Project ownership within WP |
| Researcher | `researcher` | Contribution to projects |
| Student | `student` | Limited contribution |
| Editor | `editor` | Content editing |
| Viewer | `viewer` | Read-only access |

### Resource Responsibilities (RACI)

Fine-grained permissions are assigned per resource using the RACI model:

- **R** (Responsible): Does the work, can edit
- **A** (Accountable): Decision maker, full control
- **C** (Consulted): Provides input, read-only
- **I** (Informed): Kept updated, read-only

**Resource Types**: `scientific_project`, `project_activity`, `publication`, `work_package`

### Authorization Flow

1. **Request arrives** at protected endpoint (e.g., `PUT /api/scientific-projects/42`)
2. **Extract user** from JWT via `get_current_user()` dependency
3. **Load resource** from database
4. **Load RACI assignments** for the resource
5. **Call `can(user, "update", resource, responsibilities)`**
6. **Evaluate rules** in priority order:
   - Super admin override → Allow
   - Resource ownership → Allow
   - RACI A/R role → Allow
   - Work Package scope + role → Allow/Deny
7. **Return result** (200 OK or 403 Forbidden)

**See**: [Authorization Guide](../guides/authorization.md) for comprehensive documentation.

## Database Migrations

Managed with **Alembic**:

```bash
# Create new migration
.venv/bin/alembic revision --autogenerate -m "Add new field"

# Apply migrations
.venv/bin/alembic upgrade head

# Rollback one migration
.venv/bin/alembic downgrade -1

# Show current version
.venv/bin/alembic current
```

**Migration Files**: `alembic/versions/`

**Best Practices**:
- Always review autogenerated migrations before applying
- Test migrations on a copy of production data
- Never edit applied migrations; create new ones instead

## Environment Configuration

Required environment variables in `.env`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cecan_db

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Services
GOOGLE_API_KEY=your-google-api-key

# CORS
ALLOWED_ORIGINS=http://localhost:5173
```

Load configuration via `config.py`:

```python
from config import DATABASE_URL, SECRET_KEY, JWT_EXPIRATION_MINUTES
```

## API Documentation

When the backend is running, interactive API docs are available:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Testing

Run tests with pytest:

```bash
# All tests
.venv/bin/python -m pytest tests/

# Specific test file
.venv/bin/python -m pytest tests/test_auth.py

# With coverage
.venv/bin/python -m pytest --cov=services tests/
```

**Test Structure**:
```
tests/
├── test_auth.py           # Authentication tests
├── test_authz.py          # Authorization tests
├── test_publications.py   # Publication CRUD tests
└── conftest.py            # Pytest fixtures
```

## Performance Considerations

### Database Query Optimization

1. **Eager Loading**: Use `joinedload()` to prevent N+1 queries
   ```python
   projects = db.query(ScientificProject)\
       .options(joinedload(ScientificProject.members))\
       .all()
   ```

2. **Indexes**: Key indexes on `responsibility_assignments`:
   - `(resource_type, resource_id)` for resource lookups
   - `(member_id)` for user-specific queries

3. **Batch Operations**: Use `bulk_insert_mappings()` for large datasets

### Caching

- **JWT Validation**: Token signatures are verified per request (stateless)
- **FAISS Vector Store**: Publication embeddings cached in memory
- **Future**: Consider Redis for session data and API response caching

## Security

### Password Storage

- Passwords hashed with **bcrypt** (cost factor: 12)
- Never store plaintext passwords
- Use `get_password_hash()` for registration, `verify_password()` for login

### JWT Tokens

- Signed with HS256 algorithm
- Include user email in `sub` claim
- Expire after configured time (default: 30 minutes)
- No refresh token mechanism (users re-login on expiry)

### SQL Injection Prevention

- **Always use SQLAlchemy ORM** or parameterized queries
- Never concatenate user input into SQL strings
- Example:
  ```python
  # ✅ SAFE
  user = db.query(User).filter(User.email == email).first()

  # ❌ UNSAFE
  db.execute(f"SELECT * FROM users WHERE email = '{email}'")
  ```

### CORS Configuration

- Restrict `allow_origins` to known frontend domains
- In production, replace `["*"]` with specific origins
- Enable `allow_credentials=True` for cookie-based auth

## Error Handling

### HTTP Exceptions

Use FastAPI's `HTTPException` for standard errors:

```python
from fastapi import HTTPException

# 404 Not Found
if not project:
    raise HTTPException(status_code=404, detail="Project not found")

# 403 Forbidden
if not can(user, "update", project):
    raise HTTPException(status_code=403, detail="Permission denied")

# 400 Bad Request
if not data.title:
    raise HTTPException(status_code=400, detail="Title is required")
```

### Database Errors

Handle SQLAlchemy exceptions:

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(user)
    db.commit()
except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=400, detail="Email already exists")
```

## Related Documentation

- **[Authorization Guide](../guides/authorization.md)**: Comprehensive RBAC + RACI documentation
- **[CLAUDE.md](../../CLAUDE.md)**: Quick reference and development commands
- **API Docs**: http://localhost:8000/docs

---

**Last Updated**: 2025-01-23
