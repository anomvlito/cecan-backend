from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
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
    document_paths: Optional[str] = None # JSON string

class AcademicMemberBase(BaseModel):
    rut: Optional[str] = None
    full_name: str
    email: Optional[EmailStr] = None
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
    email: Optional[EmailStr] = None
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
    nombre: str
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

class PublicationOut(BaseModel):
    id: int
    title: str = Field(..., alias="titulo")
    year: Optional[str] = Field(None, alias="fecha")
    url: Optional[str] = Field(None, alias="url_origen")
    doi: Optional[str] = Field(None, alias="canonical_doi")
    
    # New Fields
    metrics_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True

class PublicationUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[str] = None
    url: Optional[str] = None
    url_origen: Optional[str] = None
    doi: Optional[str] = None
    canonical_doi: Optional[str] = None
    resumen_es: Optional[str] = None
    resumen_en: Optional[str] = None
    author_ids: Optional[List[int]] = None
    
    class Config:
        from_attributes = True

