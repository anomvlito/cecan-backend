"""
SQLAlchemy Models for CECAN Platform
Database models implementing authentication, compliance, and administrative management.
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey, DateTime, Enum as SQLEnum, Float, JSON, Date
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
    ADMIN = "admin"           # Full system access, can manage users
    EDITOR = "editor"         # Can edit data, run sync, manage content
    VIEWER = "viewer"         # Read-only access


class User(Base):
    """User accounts with role-based access control."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    # Relationships
    # supervised_students = relationship("Student", back_populates="tutor", foreign_keys="Student.tutor_id")
    

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
    jif = Column(Float, nullable=True) # Journal Impact Factor
    is_international_collab = Column(Boolean, default=False)
    
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
    categories = Column(Text)                     # Lista separada por pipe
    ranking_category = Column(Text)               # Categoría del mejor ranking
    publisher = Column(Text)
    country = Column(String(100))
    full_ranking_raw = Column(Text)
    source_url = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)


if __name__ == "__main__":
    # Create all tables when running this module directly
    create_all_tables()

