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
    url_foto: Optional[str] = None

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

class AcademicMemberOut(AcademicMemberBase):
    id: int
    created_at: Optional[datetime] = None
    researcher_details: Optional[ResearcherDetailsOut] = None
    student_details: Optional[StudentDetailsOut] = None

    class Config:
        from_attributes = True
