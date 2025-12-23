"""
SQLAlchemy Models for CECAN Platform
Database models implementing authentication, compliance, and administrative management.
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, ForeignKey, DateTime, Enum as SQLEnum, Float
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


class Publication(Base):
    """Scientific publications with compliance audit fields."""
    __tablename__ = "publicaciones"
    
    # Basic information
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(Text, nullable=False)
    fecha = Column(String(50), nullable=True)
    autores = Column(Text, nullable=True)
    categoria = Column(String(100), nullable=True)
    url_origen = Column(Text, nullable=True)
    canonical_doi = Column(String(100), unique=True, nullable=True, index=True)  # Normalized DOI
    path_pdf_local = Column(Text, nullable=True)
    contenido_texto = Column(Text, nullable=True)
    
    # AI-generated summaries
    resumen_es = Column(Text, nullable=True)
    resumen_en = Column(Text, nullable=True)
    
    # Metadata Enrichment
    extracted_orcids = Column(Text, nullable=True)  # Comma-separated list of ORCIDs found in PDF

    # COMPLIANCE AUDIT FIELDS (El Robot)
    has_valid_affiliation = Column(Boolean, default=False, nullable=False)
    has_funding_ack = Column(Boolean, default=False, nullable=False)
    anid_report_status = Column(String(50), default="Pending", nullable=False)
    
    # Audit metadata
    last_audit_date = Column(DateTime, nullable=True)
    audit_notes = Column(Text, nullable=True)  # Automated observations
    
    # DOI Verification (Schema First: Added for Smart Audit)
    doi_verification_status = Column(String(50), default="pending", nullable=False) # pending, valid_openalex, valid_http, broken, repaired
    
    # Relationships
    researcher_connections = relationship("ResearcherPublication", back_populates="publication")
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
    wp_id = Column(Integer, ForeignKey("wps.id"), nullable=True)
    
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
    wp_id = Column(Integer, ForeignKey("wps.id"), primary_key=True)


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
    
    member = relationship("AcademicMember", back_populates="student_details", foreign_keys=[member_id])
    tutor = relationship("AcademicMember", foreign_keys=[tutor_id])
    co_tutor = relationship("AcademicMember", foreign_keys=[co_tutor_id])


class MeetingMinute(Base):
    """Meeting minutes with AI transcription and summarization."""
    __tablename__ = "meeting_minutes"
    
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=False, default=datetime.utcnow)
    titulo = Column(String(255), nullable=True)  # Optional meeting title
    audio_path = Column(Text, nullable=True)  # Path to audio file
    transcription_text = Column(Text, nullable=True)  # Full transcription
    resumen_ia = Column(Text, nullable=True)  # AI-generated summary
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExternalMetric(Base):
    """Raw metrics from external sources (e.g., OpenAlex, Google Scholar)."""
    __tablename__ = "external_metrics"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=True) # Made nullable as per plan flexibility
    publication_id = Column(Integer, ForeignKey("publicaciones.id"), nullable=True) # New field
    
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
    publication_id = Column(Integer, ForeignKey("publicaciones.id"), nullable=False, unique=True)
    
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
    __tablename__ = "wps"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(255), nullable=False)
    
    # Relationships
    projects = relationship("Project", back_populates="wp")
    members = relationship("AcademicMember", back_populates="wp") # Legacy One-to-Many
    members_list = relationship("AcademicMember", secondary="member_wps", back_populates="wps") # New Many-to-Many


class Project(Base):
    """Research projects."""
    __tablename__ = "proyectos"
    
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(Text, nullable=False)
    wp_id = Column(Integer, ForeignKey("wps.id"), nullable=True)
    
    # Relationships
    wp = relationship("WorkPackage", back_populates="projects")
    researcher_connections = relationship("ProjectResearcher", back_populates="project")
    node_connections = relationship("ProjectNode", back_populates="project")
    other_wp_connections = relationship("ProjectOtherWP", back_populates="project")


class ProjectResearcher(Base):
    """Many-to-many relationship between projects and academic members (researchers)."""
    __tablename__ = "proyecto_investigador"
    
    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    rol = Column(String(50), nullable=True)  # e.g., "Responsable", "Principal", "Colaborador"
    
    # Relationships
    project = relationship("Project", back_populates="researcher_connections")
    member = relationship("AcademicMember", back_populates="project_connections")


class ResearcherPublication(Base):
    """Many-to-many relationship between academic members and publications."""
    __tablename__ = "investigador_publicacion"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("academic_members.id"), nullable=False)
    publicacion_id = Column(Integer, ForeignKey("publicaciones.id"), nullable=False)
    match_score = Column(Integer, nullable=True)  # 0-100 confidence score
    match_method = Column(String(50), nullable=True)  # e.g., "exact_name", "fuzzy_match"
    
    # Relationships
    member = relationship("AcademicMember", back_populates="publication_connections")
    publication = relationship("Publication", back_populates="researcher_connections")


class Node(Base):
    """Thematic nodes (cancer types and cross-cutting themes)."""
    __tablename__ = "nodos"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), unique=True, nullable=False)
    
    # Relationships
    project_connections = relationship("ProjectNode", back_populates="node")


class ProjectNode(Base):
    """Many-to-many relationship between projects and nodes."""
    __tablename__ = "proyecto_nodo"
    
    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    nodo_id = Column(Integer, ForeignKey("nodos.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="node_connections")
    node = relationship("Node", back_populates="project_connections")


class ProjectOtherWP(Base):
    """Many-to-many relationship for collaborative WP connections."""
    __tablename__ = "proyecto_otrowp"
    
    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    wp_id = Column(Integer, ForeignKey("wps.id"), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="other_wp_connections")


# ===========================
# RAG SYSTEM (Vector Database)
# ===========================

class PublicationChunk(Base):
    """Text chunks with embeddings for semantic search."""
    __tablename__ = "publication_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    publicacion_id = Column(Integer, ForeignKey("publicaciones.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Sequential index within document
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # Serialized vector (BLOB in SQLite, or JSON)
    
    # Relationships
    publication = relationship("Publication", back_populates="chunks")


# ===========================
# DATABASE SETUP UTILITIES
# ===========================

def get_engine(db_path="cecan.db"):
    """Create SQLAlchemy engine."""
    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_session(db_path="cecan.db"):
    """Get database session."""
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session()


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


if __name__ == "__main__":
    # Create all tables when running this module directly
    create_all_tables()
