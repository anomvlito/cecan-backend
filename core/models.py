"""
SQLAlchemy Models for CECAN Platform
Database models implementing authentication, compliance, and administrative management.
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey, DateTime, Enum as SQLEnum, Float, JSON, Date, func, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


# ===========================
# SECURITY & AUTHENTICATION
# ===========================

class UserRole(str, enum.Enum):
    """User role enumeration for RBAC."""
    SUPER_ADMIN = "super_admin"  # Full system access, dangerous operations allowed
    ADMIN = "admin"           # Full system access, can manage users
    STAFF = "staff"           # Administrative staff (secretaría)
    PI = "pi"                 # Principal Investigator
    RESEARCHER = "researcher" # Researcher with limited access
    STUDENT = "student"       # Student with minimal access
    EDITOR = "editor"         # Can edit data, run sync, manage content (legacy)
    VIEWER = "viewer"         # Read-only access


class RaciRole(str, enum.Enum):
    """RACI responsibility roles."""
    R = "R"  # Responsible - Does the work
    A = "A"  # Accountable - Ultimately answerable
    C = "C"  # Consulted - Provides input
    I = "I"  # Informed - Kept in the loop


class ResourceType(str, enum.Enum):
    """Types of resources that can have responsibility assignments."""
    SCIENTIFIC_PROJECT = "scientific_project"
    PROJECT_ACTIVITY = "project_activity"
    PUBLICATION = "publication"
    WORK_PACKAGE = "work_package"


class User(Base):
    """User accounts with role-based access control."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    # Use values_callable to ensure enum values (e.g., "pi") are used instead of names (e.g., "PI")
    role = Column(SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    @property
    def academic_member(self):
        """
        Get the AcademicMember linked by email.
        This is populated by auth_service.get_user_by_email() for performance.
        """
        return getattr(self, '_academic_member', None)


class ResponsibilityAssignment(Base):
    """
    RACI responsibility assignments for resources.

    This table links academic members to resources (projects, activities, publications, etc.)
    with specific RACI roles, providing a flexible authorization model.
    """
    __tablename__ = "responsibility_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Resource identification
    resource_type = Column(SQLEnum(ResourceType), nullable=False, index=True)
    resource_id = Column(Integer, nullable=False, index=True)

    # RACI role
    raci_role = Column(SQLEnum(RaciRole), nullable=False, index=True)

    # Assignment to organizational entity (mandatory)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False, index=True)

    # Optional link to user account (for login-based access)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Audit metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    member = relationship("AcademicMember", foreign_keys=[member_id], backref="responsibilities")
    user = relationship("User", foreign_keys=[user_id], backref="responsibilities")
    creator = relationship("User", foreign_keys=[created_by])

    # Composite unique constraint to prevent duplicate assignments
    __table_args__ = (
        # Ensure unique (resource_type, resource_id, member_id, raci_role) combinations
        # This prevents assigning the same RACI role twice to the same member on the same resource
        Index('idx_resource_lookup', 'resource_type', 'resource_id'),
        Index('idx_member_lookup', 'member_id'),
        Index('idx_user_lookup', 'user_id'),
    )


# ===========================
# COMPLIANCE & AUDIT ("EL ROBOT")
# ===========================


class ComplianceStatus(str, enum.Enum):
    """Compliance validation status for ANID reporting."""
    OK = "Ok"                 # Fully compliant
    WARNING = "Warning"       # Missing optional information
    ERROR = "Error"           # Missing required information


class Journal(Base):
    """Scientific journals with impact metrics."""
    __tablename__ = "journals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    publisher = Column(String(255), nullable=True)
    issn = Column(String(50), nullable=True)
    metrics_source = Column(String(50), default="UNKNOWN") # WOS, SCOPUS, ESTIMATED
    
    # Web of Science (JCR) Metrics
    jif_current = Column(Float, nullable=True)
    jif_year = Column(Integer, nullable=True)
    jif_5year = Column(Float, nullable=True)
    
    # Scopus Metrics
    scopus_citescore = Column(Float, nullable=True)
    scopus_sjr = Column(Float, nullable=True)
    scopus_snip = Column(Float, nullable=True)
    
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    categories = relationship("JournalCategory", back_populates="journal", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="journal")


class JournalCategory(Base):
    """Journal rankings per category."""
    __tablename__ = "journal_categories"

    id = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=False)
    
    category_name = Column(String(255), nullable=False)
    source = Column(String(50), default="WOS") # WOS or SCOPUS
    ranking = Column(String(50), nullable=True) # e.g. "8 / 137"
    quartile = Column(String(10), nullable=True) # Q1, Q2, Q3, Q4
    percentile = Column(Float, nullable=True) # e.g. 94.5
    
    journal = relationship("Journal", back_populates="categories")


class Publication(Base):
    """Scientific publications with compliance audit fields."""
    __tablename__ = "publications"
    
    # Basic information
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False) # Renamed from titulo
    year = Column(String(50), nullable=True) # Renamed from fecha
    authors = Column(Text, nullable=True) # Renamed from autores
    category = Column(String(100), nullable=True) # Renamed from categoria
    url = Column(Text, nullable=True) # Renamed from url_origen
    canonical_doi = Column(String(100), unique=True, nullable=True, index=True)  # Normalized DOI
    has_doi = Column(Boolean, default=False, nullable=False, index=True)  # Pre-computed flag for performance
    local_path = Column(Text, nullable=True) # Renamed from path_pdf_local
    content = Column(Text, nullable=True) # Renamed from contenido_texto
    
    # AI-generated summaries
    summary_es = Column(Text, nullable=True) # Renamed from resumen_es
    summary_en = Column(Text, nullable=True) # Renamed from resumen_en
    
    # Metadata Enrichment
    extracted_orcids = Column(Text, nullable=True)  # Comma-separated list of ORCIDs found in PDF
    author_metadata = Column(JSON, nullable=True)  # Stores author names and countries from ORCID API
    ai_journal_analysis = Column(JSON, nullable=True)  # AI-extracted journal metadata and quartile estimation
    quartile = Column(String(10), nullable=True, index=True) # Dedicated column for filtering (Q1, Q2, Q3, Q4)
    
    # New Fields for Refactor (Phase 1, 2, 3)
    enrichment_status = Column(String(50), default="metadata_only", nullable=False, index=True)
    last_enrichment_at = Column(DateTime, nullable=True)
    journal_name_temp = Column(Text, nullable=True) # Temporary journal name from OpenAlex
    publisher_temp = Column(Text, nullable=True)    # Temporary publisher name

    # COMPLIANCE AUDIT FIELDS (El Robot)
    has_valid_affiliation = Column(Boolean, default=False, nullable=False)
    has_funding_ack = Column(Boolean, default=False, nullable=False)
    anid_report_status = Column(String(50), default="Pending", nullable=False)
    
    # Audit metadata
    last_audit_date = Column(DateTime, nullable=True)
    audit_notes = Column(Text, nullable=True)  # Automated observations
    
    # DOI Verification (Schema First: Added for Smart Audit)
    doi_verification_status = Column(String(50), default="pending", nullable=False) # pending, valid_openalex, valid_http, broken, repaired
    
    
    # External Metrics (OpenAlex, etc)
    metrics_data = Column(JSON, nullable=True) # Renamed from external_metrics to avoid conflict
    metrics_last_updated = Column(DateTime, nullable=True)

    # Relationships
    journal_id = Column(Integer, ForeignKey("journals.id"), nullable=True)
    journal = relationship("Journal", back_populates="publications")
    
    researcher_connections = relationship("ResearcherPublication", back_populates="publication", cascade="all, delete-orphan")
    chunks = relationship("PublicationChunk", back_populates="publication", cascade="all, delete-orphan")
    impact_metrics = relationship("PublicationImpact", uselist=False, back_populates="publication", cascade="all, delete-orphan")

    @property
    def summary(self):
        return self.summary_es or self.summary_en




# ===========================
# ACADEMIC MEMBERS (Unified Model)
# ===========================

class MemberType(str, enum.Enum):
    """Type of academic member."""
    RESEARCHER = "researcher"
    STUDENT = "student"
    STAFF = "staff"


class AcademicMember(Base):
    """Unified table for all people in the organization."""
    __tablename__ = "academic_members"
    
    id = Column(Integer, primary_key=True, index=True)
    rut = Column(String(12), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    institution = Column(String(255), nullable=True)
    member_type = Column(String(50), nullable=False)
    
    # WP Affiliation (Everyone belongs to a WP)
    wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True)
    
    # Computed/Status fields
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wp = relationship("WorkPackage", back_populates="members")
    researcher_details = relationship("ResearcherDetails", uselist=False, back_populates="member", cascade="all, delete-orphan")
    student_details = relationship("StudentDetails", uselist=False, back_populates="member", cascade="all, delete-orphan", foreign_keys="StudentDetails.member_id")
    
    # Connections (Polymorphic-like)
    publication_connections = relationship("ResearcherPublication", back_populates="member")
    project_connections = relationship("ProjectResearcher", back_populates="member")
    
    # Many-to-Many with WPs
    wps = relationship("WorkPackage", secondary="member_wps", back_populates="members_list")
    
    # Metrics
    external_metrics = relationship("ExternalMetric", back_populates="member", cascade="all, delete-orphan")


class MemberWP(Base):
    """Many-to-many relationship between academic members and WPs."""
    __tablename__ = "member_wps"
    
    member_id = Column(Integer, ForeignKey("academic_members.id"), primary_key=True)
    wp_id = Column(Integer, ForeignKey("work_packages.id"), primary_key=True)


class ResearcherDetails(Base):
    """Specific details for Researchers."""
    __tablename__ = "researcher_details"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    
    # Identity & Metadata
    orcid = Column(String(50), unique=True, nullable=True, index=True)
    is_auditable = Column(Boolean, default=True)  # False if no ORCID
    last_openalex_sync = Column(DateTime, nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    name_variations = Column(Text, nullable=True)  # Pipe-separated variations

    category = Column(String(50), nullable=True)  # Principal, Asociado, Adjunto
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    formalized_exit = Column(Boolean, default=False)
    
    # Academic Metrics
    citaciones_totales = Column(Integer, nullable=True)
    indice_h = Column(Integer, nullable=True)
    works_count = Column(Integer, nullable=True)  # OpenAlex: Total publications
    i10_index = Column(Integer, nullable=True)    # OpenAlex: Publications with ≥10 citations
    url_foto = Column(Text, nullable=True)
    
    member = relationship("AcademicMember", back_populates="researcher_details")


class StudentDetails(Base):
    """Specific details for Students."""
    __tablename__ = "student_details"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    
    # Supervision (Self-referential to AcademicMember)
    tutor_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
    co_tutor_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
    
    thesis_title = Column(Text, nullable=True)
    program = Column(String(255), nullable=True)
    university = Column(String(255), nullable=True)
    funding_source = Column(String(255), nullable=True)
    
    # Dates
    program_start = Column(DateTime, nullable=True)
    thesis_start = Column(DateTime, nullable=True)
    defense_date = Column(DateTime, nullable=True)
    
    # Documents (JSON paths)
    document_paths = Column(Text, nullable=True)  # JSON: {cert_validity: "path", thesis: "path"}
    
    # Document Management (ANID Reporting)
    thesis_enrollment_document = Column(Text, nullable=True)  # Path to thesis enrollment with CECAN mark
    thesis_enrollment_verified = Column(Boolean, default=False)  # Admin verified CECAN mark
    regular_student_certificate = Column(Text, nullable=True)  # Path to regular student certificate
    certificate_valid_until = Column(Date, nullable=True)  # Certificate expiration date
    additional_documents = Column(JSON, nullable=True)  # {type: path} for other docs
    documents_complete = Column(Boolean, default=False)  # All required docs present & verified
    
    member = relationship("AcademicMember", back_populates="student_details", foreign_keys=[member_id])
    tutor = relationship("AcademicMember", foreign_keys=[tutor_id])
    co_tutor = relationship("AcademicMember", foreign_keys=[co_tutor_id])


class MeetingMinute(Base):
    """Meeting minutes with AI transcription and summarization."""
    __tablename__ = "meeting_minutes"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)  # Renamed from fecha
    title = Column(String(255), nullable=True)  # Renamed from titulo
    audio_path = Column(Text, nullable=True)  # Path to audio file
    transcription_text = Column(Text, nullable=True)  # Full transcription
    ai_summary = Column(Text, nullable=True)  # Renamed from resumen_ia
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExternalMetric(Base):
    """Raw metrics from external sources (e.g., OpenAlex, Google Scholar)."""
    __tablename__ = "external_metrics"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True) # Made nullable as per plan flexibility
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=True) # New field
    
    source = Column(String(50), nullable=False) # e.g., 'openalex', 'scholar'
    metric_type = Column(String(50), nullable=False) # e.g., 'h_index', 'i10_index', 'citation_count'
    value = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow) # Renamed from fetched_at
    
    member = relationship("AcademicMember", back_populates="external_metrics")
    publication = relationship("Publication", backref="external_metrics") # Simple backref for now



class IngestionAudit(Base):
    """Audit log for data ingestion processes."""
    __tablename__ = "ingestion_audit"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False) # e.g., 'sync_publications', 'update_metrics'
    status = Column(String(50), nullable=False) # 'success', 'failed', 'partial'
    payload_summary = Column(Text, nullable=True) # JSON summary of what was processed
    timestamp = Column(DateTime, default=datetime.utcnow)


class PublicationImpact(Base):
    """Impact metrics for specific publications."""
    __tablename__ = "publication_impact"

    id = Column(Integer, primary_key=True, index=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False, unique=True)
    
    citation_count = Column(Integer, default=0)
    quartile = Column(String(10), nullable=True) # Q1, Q2, etc.
    ranking_percentile = Column(Float, nullable=True)  # e.g., 81.4 (from WOS Mirror)
    jif = Column(Float, nullable=True) # Journal Impact Factor
    is_international_collab = Column(Boolean, default=False)
    
    # WOS Mirror Integration
    source = Column(String(50), nullable=True)  # 'wos_mirror', 'openalex', 'manual'
    match_confidence = Column(String(50), nullable=True)  # 'exact_issn', 'exact_name_verified', etc.
    wos_journal_id = Column(Integer, nullable=True)  # FK to wos_journal_mirror
    
    publication = relationship("Publication", back_populates="impact_metrics")



# ===========================
# PROJECTS & ORGANIZATION
# ===========================

class WorkPackage(Base):
    """Work packages (WP) - thematic research groups."""
    __tablename__ = "work_packages"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False) # Renamed from nombre
    
    # Relationships
    projects = relationship("Project", back_populates="wp")
    members = relationship("AcademicMember", back_populates="wp") # Legacy One-to-Many
    members_list = relationship("AcademicMember", secondary="member_wps", back_populates="wps") # New Many-to-Many


class Project(Base):
    """Research projects."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False) # Renamed from titulo
    wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True)
    
    # Relationships
    wp = relationship("WorkPackage", back_populates="projects")
    researcher_connections = relationship("ProjectResearcher", back_populates="project")
    node_connections = relationship("ProjectNode", back_populates="project")
    other_wp_connections = relationship("ProjectOtherWP", back_populates="project")


class ProjectResearcher(Base):
    """Many-to-many relationship between projects and academic members (researchers)."""
    __tablename__ = "project_researchers"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    role = Column(String(50), nullable=True)  # Renamed from rol
    
    # Relationships
    project = relationship("Project", back_populates="researcher_connections")
    member = relationship("AcademicMember", back_populates="project_connections")


class ResearcherPublication(Base):
    """Many-to-many relationship between academic members and publications."""
    __tablename__ = "researcher_publications"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    match_score = Column(Integer, nullable=True)  # 0-100 confidence score
    match_method = Column(String(50), nullable=True)  # e.g., "exact_name", "fuzzy_match"
    
    # Relationships
    member = relationship("AcademicMember", back_populates="publication_connections")
    publication = relationship("Publication", back_populates="researcher_connections")


class Node(Base):
    """Thematic nodes (cancer types and cross-cutting themes)."""
    __tablename__ = "nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False) # Renamed from nombre
    
    # Relationships
    project_connections = relationship("ProjectNode", back_populates="node")


class ProjectNode(Base):
    """Many-to-many relationship between projects and nodes."""
    __tablename__ = "project_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="node_connections")
    node = relationship("Node", back_populates="project_connections")


class ProjectOtherWP(Base):
    """Many-to-many relationship for collaborative WP connections."""
    __tablename__ = "project_other_wps"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="other_wp_connections")


# ===========================
# RAG SYSTEM (Vector Database)
# ===========================

class PublicationChunk(Base):
    """Text chunks with embeddings for semantic search."""
    __tablename__ = "publication_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Sequential index within document
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # Serialized vector (BLOB in SQLite, or JSON)
    
    # Relationships
    publication = relationship("Publication", back_populates="chunks")


# ===========================
# STUDENT MANAGEMENT & THESES
# ===========================

class StudentProgram(str, enum.Enum):
    """Programs offered by CECAN."""
    MAGISTER = "Magister"
    DOCTORADO = "Doctorado"
    POSTDOC = "Postdoctorado"
    OTHER = "Other"

class StudentStatus(str, enum.Enum):
    """Student academic status."""
    ACTIVE = "Activo"
    GRADUATED = "Graduado"
    WITHDRAWN = "Retirado"
    SUSPENDED = "Suspendido"

class ThesisStatus(str, enum.Enum):
    """Thesis progress status."""
    PROPOSAL = "Propuesta"
    DRAFT = "Borrador"
    DEFENSE_PENDING = "Defensa Pendiente"
    APPROVED = "Aprobada"

class Student(Base):
    """Students supervised by CECAN members."""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    rut = Column(String(20), nullable=True)  # Chilean ID
    
    program = Column(String(255), nullable=True) # Changed from Enum to String to support original names
    university = Column(String(255), nullable=True)
    start_date = Column(DateTime, nullable=True)
    graduation_date = Column(DateTime, nullable=True)
    
    status = Column(String(50), default="Activo", nullable=False) # Changed from Enum to String
    
    # WP Affiliation
    wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True)
    wp = relationship("WorkPackage")
    
    # Relationships
    tutor_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
    tutor = relationship("AcademicMember", foreign_keys=[tutor_id], backref="students_supervised")
    tutor_name = Column(String(255), nullable=True) # Explicit name from import
    
    co_tutor_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
    co_tutor = relationship("AcademicMember", foreign_keys=[co_tutor_id], backref="students_co_supervised")
    co_tutor_name = Column(String(255), nullable=True) # Explicit name from import
    
    theses = relationship("Thesis", back_populates="student", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Thesis(Base):
    """Theses produced by students."""
    __tablename__ = "theses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text, nullable=True)
    
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    student = relationship("Student", back_populates="theses")
    
    status = Column(SQLEnum(ThesisStatus), default=ThesisStatus.PROPOSAL, nullable=False)
    defense_date = Column(DateTime, nullable=True)
    file_url = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===========================
# DATABASE SETUP UTILITIES
# ===========================
# GANTT CHART MANAGEMENT (Advanced Scheduling)
# ===========================
# REMOVED: Gantt tables deleted 2026-01-25 - Using project_activities instead
# See migration: cc2078af8b8c_remove_gantt_tables.py

# class GanttTaskStatus(str, enum.Enum):
#     """Status for Gantt tasks with traffic light logic."""
#     PENDING = "pending"           # Not started
#     IN_PROGRESS = "in_progress"   # Currently being worked on
#     LATE = "late"                 # Past due date with incomplete progress
#     COMPLETED = "completed"       # 100% done
#     ON_HOLD = "on_hold"           # Paused
#
#
# class GanttAlertType(str, enum.Enum):
#     """Types of alerts for project health monitoring."""
#     PREVENTIVE = "preventive"         # Task due soon
#     LATE = "late"                     # Task overdue
#     FINANCIAL_DISCREPANCY = "financial_discrepancy"  # Budget vs progress mismatch
#     MILESTONE_RISK = "milestone_risk" # Milestone at risk
#
#
# class GanttTask(Base):
#     """
#     Gantt chart tasks with hierarchical WBS structure.
#     Supports budget tracking for financial control objectives.
#     """
#     __tablename__ = "gantt_tasks"
#
#     id = Column(Integer, primary_key=True, index=True)
#
#     # Hierarchy (WBS - Work Breakdown Structure)
#     parent_id = Column(Integer, ForeignKey("gantt_tasks.id"), nullable=True, index=True)
#     wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True, index=True)
#     sort_order = Column(Integer, default=0)  # For ordering within same parent
#     wbs_code = Column(String(50), nullable=True)  # e.g., "1.2.3"
#
#     # Task Details
#     text = Column(Text, nullable=False)  # Task name/description
#     start_date = Column(DateTime, nullable=False)
#     end_date = Column(DateTime, nullable=False)
#     duration = Column(Integer, nullable=False)  # In days
#     progress = Column(Float, default=0.0)  # 0.0 to 1.0
#
#     # Financial Control (New Requirement)
#     budget_allocated = Column(Float, default=0.0)  # Planned budget
#     budget_executed = Column(Float, default=0.0)   # Actual spent
#
#     # Status & Classification
#     status = Column(SQLEnum(GanttTaskStatus), default=GanttTaskStatus.PENDING, nullable=False)
#     task_type = Column(String(50), default="task")  # task, milestone, project
#     priority = Column(Integer, default=2)  # 1=High, 2=Medium, 3=Low
#
#     # Ownership
#     owner_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
#
#     # Metadata
#     notes = Column(Text, nullable=True)
#     color = Column(String(20), nullable=True)  # Custom color override
#     is_readonly = Column(Boolean, default=False)  # Lock past tasks
#
#     # Audit
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
#     created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
#
#     # Relationships
#     parent = relationship("GanttTask", remote_side=[id], backref="children")
#     wp = relationship("WorkPackage", backref="gantt_tasks")
#     owner = relationship("AcademicMember", backref="assigned_tasks")
#     links_from = relationship("GanttLink", foreign_keys="GanttLink.source_id", back_populates="source", cascade="all, delete-orphan")
#     links_to = relationship("GanttLink", foreign_keys="GanttLink.target_id", back_populates="target", cascade="all, delete-orphan")
#
#
# class GanttLink(Base):
#     """
#     Dependencies between Gantt tasks.
#     Supports finish-to-start, start-to-start, etc.
#     """
#     __tablename__ = "gantt_links"
#
#     id = Column(Integer, primary_key=True, index=True)
#     source_id = Column(Integer, ForeignKey("gantt_tasks.id"), nullable=False)
#     target_id = Column(Integer, ForeignKey("gantt_tasks.id"), nullable=False)
#     link_type = Column(String(10), default="0")  # 0=FS, 1=SS, 2=FF, 3=SF
#     lag = Column(Integer, default=0)  # Days of lag/lead time
#
#     # Relationships
#     source = relationship("GanttTask", foreign_keys=[source_id], back_populates="links_from")
#     target = relationship("GanttTask", foreign_keys=[target_id], back_populates="links_to")
#
#
# class GanttAlert(Base):
#     """
#     Automated alerts for project health monitoring.
#     Generated by check_project_health() utility.
#     """
#     __tablename__ = "gantt_alerts"
#
#     id = Column(Integer, primary_key=True, index=True)
#     task_id = Column(Integer, ForeignKey("gantt_tasks.id"), nullable=False)
#
#     alert_type = Column(SQLEnum(GanttAlertType), nullable=False)
#     severity = Column(String(20), default="warning")  # info, warning, critical
#     message = Column(Text, nullable=False)
#
#     # Financial context (for discrepancy alerts)
#     budget_variance = Column(Float, nullable=True)  # % over/under budget
#     progress_variance = Column(Float, nullable=True)  # Expected vs actual progress
#
#     # Status
#     is_acknowledged = Column(Boolean, default=False)
#     acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
#     acknowledged_at = Column(DateTime, nullable=True)
#
#     created_at = Column(DateTime, default=datetime.utcnow)
#
#     # Relationships
#     task = relationship("GanttTask", backref="alerts")
#
#
# class GanttImportLog(Base):
#     """
#     Audit log for Excel imports into Gantt system.
#     Tracks which files were imported and when.
#     """
#     __tablename__ = "gantt_import_logs"
#
#     id = Column(Integer, primary_key=True, index=True)
#     wp_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True)
#
#     filename = Column(String(255), nullable=False)
#     file_hash = Column(String(64), nullable=True)  # SHA256 for deduplication
#
#     tasks_created = Column(Integer, default=0)
#     tasks_updated = Column(Integer, default=0)
#     errors_count = Column(Integer, default=0)
#     error_details = Column(JSON, nullable=True)
#
#     imported_by = Column(Integer, ForeignKey("users.id"), nullable=True)
#     imported_at = Column(DateTime, default=datetime.utcnow)
#
#     # Relationships
#     wp = relationship("WorkPackage", backref="import_logs")


# ===========================

# LEGACY SQLITE FUNCTIONS REMOVED TO PREVENT CONFUSION
# Please use database.session.get_session instead


def create_all_tables(db_path="cecan.db"):
    """Create all tables in the database."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    print(f"All tables created successfully in {db_path}")


def drop_all_tables(db_path="cecan.db"):
    """Drop all tables (USE WITH CAUTION)."""
    engine = get_engine(db_path)
    Base.metadata.drop_all(engine)
    print(f"[WARNING] All tables dropped from {db_path}")



class WosJournalMirror(Base):
    """Mirror table for WOS Journal data (scraped)."""
    __tablename__ = "wos_journal_mirror"

    wos_id = Column(Integer, primary_key=True)           # El ID de la URL
    journal_name = Column(Text, index=True)
    status = Column(String(50))                   # Active, Discontinued
    best_quartile = Column(String(10))            # Q1, Q2, Q3, Q4, N/A
    best_ranking_percent = Column(String(20))     # Ej: "99.7%"
    jif = Column(String(20))                      # Journal Impact Factor
    five_year_jif = Column(String(20))            # 5-Year Impact Factor
    issn = Column(String(20), index=True)
    eissn = Column(String(20), index=True)
    categories = Column(JSON)                     # Array JSON de categorías parseadas
    ranking_category = Column(Text)               # Categoría del mejor ranking
    publisher = Column(Text)
    country = Column(String(100))
    full_ranking_raw = Column(Text)
    source_url = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# SCIENTIFIC PROJECT MANAGEMENT - New Clean Architecture
# =============================================================================

class WorkPackageType(str, enum.Enum):
    """Work Package categories."""
    WP1 = "WP1"
    WP2 = "WP2"
    WP3 = "WP3"
    WP4 = "WP4"
    WP5 = "WP5"
    OUTREACH = "OUTREACH"
    TRAINING = "TRAINING"
    GOVERNANCE = "GOVERNANCE"


class ProjectStatusType(str, enum.Enum):
    """Project lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActivityStatusType(str, enum.Enum):
    """Activity/Task status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class PaymentStatusType(str, enum.Enum):
    """Payment status for activity budgets."""
    PENDING = "pending"
    PAID = "paid"


class ScientificProject(Base):
    """
    Scientific Project - Main entity for research project management.

    Represents a funded research project with its metadata, budget,
    and timeline spanning specific grant years.
    """
    __tablename__ = "scientific_projects"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    title = Column(Text, nullable=False)
    code = Column(String(20), unique=True, index=True)  # e.g., "P-08"
    description = Column(Text, nullable=True)

    # Classification
    work_package = Column(SQLEnum(WorkPackageType), nullable=False)
    grant_type = Column(String(100), nullable=True)  # e.g., "Seed Research Grant"

    # Principal Investigator
    pi_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True)
    pi_name = Column(String(200), nullable=True)  # Denormalized for display

    # Timeline - Grant Years covered (1-5)
    # Stored as JSON array, e.g., [3, 4] means Year 3 and Year 4
    years_covered = Column(JSON, default=list)

    # Calculated dates based on years_covered
    # Year 1 = 2021, Year 2 = 2022, etc. (configurable base year)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Budget Control
    budget_allocated = Column(Float, default=0.0)
    budget_executed = Column(Float, default=0.0)
    currency = Column(String(10), default="CLP")

    # Status
    status = Column(SQLEnum(ProjectStatusType), default=ProjectStatusType.DRAFT)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0

    # Metadata
    color = Column(String(20), nullable=True)  # For UI display
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    activities = relationship("ProjectActivity", back_populates="project",
                             cascade="all, delete-orphan", order_by="ProjectActivity.sort_order")
    pi = relationship("AcademicMember", foreign_keys=[pi_id])

    @property
    def budget_remaining(self) -> float:
        return self.budget_allocated - self.budget_executed

    @property
    def budget_utilization(self) -> float:
        if self.budget_allocated <= 0:
            return 0.0
        return (self.budget_executed / self.budget_allocated) * 100

    @property
    def is_over_budget(self) -> bool:
        return self.budget_executed > self.budget_allocated

    def calculate_dates_from_years(self, base_year: int = 2021):
        """Calculate start/end dates from years_covered array."""
        if not self.years_covered:
            return

        min_year = min(self.years_covered)
        max_year = max(self.years_covered)

        # Year 1 = base_year, Year 2 = base_year + 1, etc.
        self.start_date = datetime(base_year + min_year - 1, 1, 1).date()
        self.end_date = datetime(base_year + max_year - 1, 12, 31).date()


class ProjectActivity(Base):
    """
    Project Activity - Individual tasks/stages within a project.

    Represents work items that need to be completed as part of the project.
    """
    __tablename__ = "project_activities"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("scientific_projects.id", ondelete="CASCADE"),
                       nullable=False, index=True)

    # Content
    number = Column(Integer, default=1)  # (1), (2), (3)...
    description = Column(Text, nullable=False)

    # Timeline
    start_month = Column(Date, nullable=True)  # First day of start month
    end_month = Column(Date, nullable=True)    # Last day of end month

    # Status
    status = Column(SQLEnum(ActivityStatusType), default=ActivityStatusType.PENDING)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0

    # Financial Control
    budget_allocated = Column(Float, default=0.0)
    payment_status = Column(SQLEnum(PaymentStatusType), default=PaymentStatusType.PENDING)
    payment_proof_url = Column(String(500), nullable=True)  # Link to uploaded proof

    # Display
    sort_order = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Relationships
    project = relationship("ScientificProject", back_populates="activities")
    creator = relationship("User", foreign_keys=[created_by])

    @property
    def duration_months(self) -> int:
        if not self.start_month or not self.end_month:
            return 0
        delta = self.end_month - self.start_month
        return max(1, (delta.days // 30) + 1)

    @property
    def formatted_number(self) -> str:
        return f"({self.number})"



# ==============================================================================
# SCHOLAR INTELLIGENCE - Embeddings & Paper Cache
# ==============================================================================

class ScholarEnrichmentStatus(str, enum.Enum):
    """Status of Scholar API enrichment for a paper."""
    PENDING = "pending"           # Not yet enriched
    ENRICHED = "enriched"         # Successfully enriched
    FAILED = "failed"             # API call failed
    NOT_FOUND = "not_found"       # DOI not found in Semantic Scholar
    RATE_LIMITED = "rate_limited" # Hit API rate limit


class ScholarPaperData(Base):
    """
    Scholar API cache and embeddings storage.
    Stores paper intelligence fetched from Semantic Scholar API.
    DOI is the primary key, linking to publications table.
    """
    __tablename__ = "scholar_paper_data"
    
    # Primary Key (DOI from publications)
    doi = Column(String(255), primary_key=True, index=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=True, index=True)
    
    # Semantic Scholar IDs
    semantic_scholar_id = Column(String(50), unique=True, nullable=True, index=True)
    
    # Core Metadata (cached from Scholar)
    title = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    authors = Column(JSON, nullable=True)  # List of {name, authorId, orcid}
    
    # AI Intelligence
    tldr = Column(Text, nullable=True)
    abstract = Column(Text, nullable=True)
    
    # Embeddings (768 dimensions from Specter model)
    # Using PostgreSQL ARRAY type for flexibility
    # Can be migrated to pgvector extension later for similarity search
    embedding_vector = Column(JSON, nullable=True)  # Stored as JSON array
    
    # Citation Metrics
    citation_count = Column(Integer, default=0)
    influential_citation_count = Column(Integer, default=0)
    
    # Citation Intelligence (JSON)
    intent_breakdown = Column(JSON, nullable=True)  # {"methodology": 5, "result": 3, "background": 2}
    smart_citations = Column(JSON, nullable=True)   # Detailed citations with intents
    
    # Reference Graph Data
    reference_nodes = Column(JSON, nullable=True)  # Graph nodes for visualization
    reference_links = Column(JSON, nullable=True)  # Graph links for visualization
    
    # Enrichment Control
    enrichment_status = Column(SQLEnum(ScholarEnrichmentStatus), 
                               default=ScholarEnrichmentStatus.PENDING, 
                               nullable=False, 
                               index=True)
    last_enriched_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    publication = relationship("Publication", backref="scholar_data")


class ResearchMapSnapshot(Base):
    __tablename__ = "research_map_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    parameters = Column(JSON)  # {n_neighbors, min_dist, n_clusters, metric}
    total_publications = Column(Integer)

    points = relationship("ResearchMapPoint", back_populates="snapshot", cascade="all, delete-orphan")


class ResearchMapPoint(Base):
    __tablename__ = "research_map_points"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("research_map_snapshots.id", ondelete="CASCADE"))
    publication_id = Column(Integer, ForeignKey("publications.id", ondelete="CASCADE"))

    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    cluster_id = Column(Integer)
    cluster_label = Column(String)

    snapshot = relationship("ResearchMapSnapshot", back_populates="points")
    publication = relationship("Publication")

if __name__ == "__main__":
    # Create all tables when running this module directly
    create_all_tables()

