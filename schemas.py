from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

# Enums
class MemberType(str, Enum):
    RESEARCHER = "researcher"
    STUDENT = "student"
    STAFF = "staff"

class ComplianceStatus(str, Enum):
    OK = "Ok"
    WARNING = "Warning"
    ERROR = "Error"

# Shared Properties
class ResearcherDetailsBase(BaseModel):
    category: Optional[str] = None
    orcid: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name_variations: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    formalized_exit: Optional[bool] = False
    citaciones_totales: Optional[int] = None
    indice_h: Optional[int] = None
    works_count: Optional[int] = None  # OpenAlex: Total publications
    i10_index: Optional[int] = None    # OpenAlex: Publications with ≥10 citations
    url_foto: Optional[str] = None
    is_auditable: bool = True
    last_openalex_sync: Optional[datetime] = None

class StudentDetailsBase(BaseModel):
    tutor_id: Optional[int] = None
    co_tutor_id: Optional[int] = None
    thesis_title: Optional[str] = None
    program: Optional[str] = None
    university: Optional[str] = None
    funding_source: Optional[str] = None
    program_start: Optional[datetime] = None
    thesis_start: Optional[datetime] = None
    defense_date: Optional[datetime] = None
    document_paths: Optional[str] = None
    
    # Document Management
    thesis_enrollment_document: Optional[str] = None
    thesis_enrollment_verified: bool = False
    regular_student_certificate: Optional[str] = None
    certificate_valid_until: Optional[date] = None
    additional_documents: Optional[dict] = None
    documents_complete: bool = False # JSON string

class AcademicMemberBase(BaseModel):
    rut: Optional[str] = None
    full_name: str
    email: Optional[str] = None # Relaxed from EmailStr to handle legacy dirty data
    institution: Optional[str] = None
    member_type: MemberType
    wp_id: Optional[int] = None
    is_active: bool = True

# Creation Schemas
class AcademicMemberCreate(AcademicMemberBase):
    researcher_details: Optional[ResearcherDetailsBase] = None
    student_details: Optional[StudentDetailsBase] = None

# Update Schemas
class AcademicMemberUpdate(BaseModel):
    rut: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    institution: Optional[str] = None
    member_type: Optional[MemberType] = None
    wp_id: Optional[int] = None
    is_active: Optional[bool] = None
    researcher_details: Optional[ResearcherDetailsBase] = None
    student_details: Optional[StudentDetailsBase] = None

# Output Schemas
class ResearcherDetailsOut(ResearcherDetailsBase):
    id: int
    member_id: int
    class Config:
        from_attributes = True

class StudentDetailsOut(StudentDetailsBase):
    id: int
    member_id: int
    class Config:
        from_attributes = True

class WorkPackageSchema(BaseModel):
    id: int
    name: str # Renamed from nombre
    class Config:
        from_attributes = True

class AcademicMemberOut(AcademicMemberBase):
    id: int
    created_at: Optional[datetime] = None
    researcher_details: Optional[ResearcherDetailsOut] = None
    student_details: Optional[StudentDetailsOut] = None
    wps: List[WorkPackageSchema] = []

    class Config:
        from_attributes = True

# Public API Schemas
class PublicationSummarySchema(BaseModel):
    id: int
    title: str
    year: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None

class ResearcherSummarySchema(BaseModel):
    id: int
    full_name: str
    avatar_url: Optional[str] = None

# Sankey Diagram Schemas
class SankeyNode(BaseModel):
    id: str
    nodeColor: Optional[str] = None

class SankeyLink(BaseModel):
    source: str
    target: str
    value: int


class SankeyData(BaseModel):
    nodes: List[SankeyNode]
    links: List[SankeyLink]

class ResearchOpportunityOut(BaseModel):
    id: int
    target_wp_id: int
    target_node_id: int
    wp_name: str
    node_name: str
    gap_description: str
    suggested_line: Optional[str] = None
    impact_potential: Optional[float] = 0.0
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class JournalCategoryOut(BaseModel):
    category_name: str
    source: str
    quartile: Optional[str]
    percentile: Optional[float]
    ranking: Optional[str]

    class Config:
        from_attributes = True

class JournalOut(BaseModel):
    id: int
    name: str
    publisher: Optional[str]
    jif_current: Optional[float]
    jif_year: Optional[int]
    jif_5year: Optional[float]
    scopus_citescore: Optional[float]
    scopus_sjr: Optional[float] 
    scopus_snip: Optional[float]
    metrics_source: Optional[str]  # ← NUEVO: "WOS" o "SCOPUS"
    last_updated: Optional[datetime]
    categories: List[JournalCategoryOut] = []

    class Config:
        from_attributes = True

# Schema para métricas de impacto (MOVIDO ARRIBA)
class PublicationImpactOut(BaseModel):
    citation_count: int = 0
    quartile: Optional[str] = None
    jif: Optional[float] = None
    ranking_percentile: Optional[float] = None
    source: Optional[str] = None
    is_international_collab: bool = False
    
    class Config:
        from_attributes = True

# Schema para la verificación WOS (MOVIDO ARRIBA)
class WosVerificationOut(BaseModel):
    match_type: str
    quartile: Optional[str] = None
    decile: Optional[int] = None
    is_top_10: bool = False
    source_url: Optional[str] = None
    categories: List[str] = []
    journal_name: Optional[str] = None

    class Config:
        from_attributes = True

class PublicationOut(BaseModel):
    id: int
    title: str
    year: Optional[str] = None
    url: Optional[str] = None
    canonical_doi: Optional[str] = None
    
    # Estado de enriquecimiento (NUEVO)
    enrichment_status: str = "metadata_only"  # ← NUEVO
    
    # Resúmenes (opcionales)
    summary_es: Optional[str] = None
    summary_en: Optional[str] = None
    
    # Relación con revista
    journal: Optional[JournalOut] = None
    
    # Metadata de OpenAlex
    metrics_data: Optional[Dict[str, Any]] = None
    
    # Impact Metrics
    impact_metrics: Optional[PublicationImpactOut] = None

    # Temporal fields for incomplete matches
    publisher_temp: Optional[str] = None
    
    # WOS Verification
    wos_verification: Optional[WosVerificationOut] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True

class PublicationUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[str] = None
    url: Optional[str] = None
    canonical_doi: Optional[str] = None
    
    # Resúmenes
    summary_es: Optional[str] = None
    summary_en: Optional[str] = None
    
    # Autores
    author_ids: Optional[List[int]] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True

# Schema detallado de author para publicación
class PublicationAuthorOut(BaseModel):
    id: int
    full_name: str
    email: Optional[str] = None
    institution: Optional[str] = None
    
    class Config:
        from_attributes = True

class PublicationDetailOut(BaseModel):
    id: int
    title: str
    year: Optional[str] = None
    url: Optional[str] = None
    canonical_doi: Optional[str] = None
    category: Optional[str] = None
    
    # Estado de enriquecimiento
    enrichment_status: str = "metadata_only"
    last_enrichment_at: Optional[datetime] = None
    
    # Resúmenes
    summary_es: Optional[str] = None
    summary_en: Optional[str] = None
    
    # Campos de auditoría
    has_valid_affiliation: bool = False
    has_funding_ack: bool = False
    anid_report_status: str = "Pending"
    last_audit_date: Optional[datetime] = None
    audit_notes: Optional[str] = None
    doi_verification_status: str = "pending"
    
    # Relación con revista
    journal: Optional[JournalOut] = None
    journal_name_temp: Optional[str] = None
    publisher_temp: Optional[str] = None
    
    # Metadata de OpenAlex
    metrics_data: Optional[Dict[str, Any]] = None
    metrics_last_updated: Optional[datetime] = None
    
    # Métricas de impacto
    impact_metrics: Optional[PublicationImpactOut] = None
    
    # Verificación WOS
    wos_verification: Optional[WosVerificationOut] = None
    
    # Autores (extraídos desde researcher_connections)
    authors: List[PublicationAuthorOut] = []
    
    @classmethod
    def from_orm(cls, obj):
        # Extract authors from researcher_connections
        authors_list = []
        if hasattr(obj, 'researcher_connections') and obj.researcher_connections:
            for conn in obj.researcher_connections:
                if conn.member:
                    authors_list.append(PublicationAuthorOut(
                        id=conn.member.id,
                        full_name=conn.member.full_name,
                        email=conn.member.email,
                        institution=conn.member.institution
                    ))
        
        # Build dict manually to avoid validation error on authors field
        data = {
            'id': obj.id,
            'title': obj.title,
            'year': obj.year,
            'url': obj.url,
            'category': obj.category,
            'canonical_doi': obj.canonical_doi,
            'doi_verification_status': obj.doi_verification_status,
            'summary_es': obj.summary_es,
            'summary_en': obj.summary_en,
            'content': obj.content,
            'has_valid_affiliation': obj.has_valid_affiliation,
            'has_funding_ack': obj.has_funding_ack,
            'anid_report_status': obj.anid_report_status,
            'last_audit_date': obj.last_audit_date,
            'audit_notes': obj.audit_notes,
            'enrichment_status': obj.enrichment_status,
            'last_enrichment_at': obj.last_enrichment_at,
            'journal': obj.journal,
            'journal_name_temp': obj.journal_name_temp,
            'publisher_temp': obj.publisher_temp,
            'quartile': obj.quartile,
            'metrics_data': obj.metrics_data,
            'metrics_last_updated': obj.metrics_last_updated,
            'impact_metrics': obj.impact_metrics,
            'wos_verification': None, # Populated manually in route
            'authors': authors_list
        }
        
        return cls(**data)
    
    class Config:
        from_attributes = True
        populate_by_name = True

# ===========================
# STUDENT MANAGEMENT SCHEMAS
# ===========================

class StudentProgramEnum(str, Enum):
    MAGISTER = "Magister"
    DOCTORADO = "Doctorado"
    POSTDOC = "Postdoctorado"
    OTHER = "Other"

class StudentStatusEnum(str, Enum):
    ACTIVE = "Activo"
    GRADUATED = "Graduado"
    WITHDRAWN = "Retirado"
    SUSPENDED = "Suspendido"

class ThesisStatusEnum(str, Enum):
    PROPOSAL = "Propuesta"
    DRAFT = "Borrador"
    DEFENSE_PENDING = "Defensa Pendiente"
    APPROVED = "Aprobada"

class ThesisBase(BaseModel):
    title: str
    abstract: Optional[str] = None
    status: ThesisStatusEnum = ThesisStatusEnum.PROPOSAL
    defense_date: Optional[datetime] = None
    file_url: Optional[str] = None

class ThesisCreate(ThesisBase):
    student_id: int

class ThesisUpdate(ThesisBase):
    title: Optional[str] = None
    status: Optional[ThesisStatusEnum] = None

class ThesisOut(ThesisBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    class Config:
        from_attributes = True

class StudentBase(BaseModel):
    full_name: str
    email: Optional[str] = None  # Relaxed from EmailStr to handle legacy dirty data
    rut: Optional[str] = None
    program: Optional[str] = None
    university: Optional[str] = None
    start_date: Optional[datetime] = None
    graduation_date: Optional[datetime] = None
    status: Optional[str] = "Activo"
    tutor_id: Optional[int] = None
    co_tutor_id: Optional[int] = None
    tutor_name: Optional[str] = None
    co_tutor_name: Optional[str] = None
    wp_id: Optional[int] = None

class StudentCreate(StudentBase):
    pass

class StudentUpdate(StudentBase):
    full_name: Optional[str] = None
    program: Optional[StudentProgramEnum] = None
    status: Optional[StudentStatusEnum] = None

class StudentOut(StudentBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    theses: List[ThesisOut] = []
    
    class Config:
        from_attributes = True


