from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
import shutil
import os
import json
from sqlalchemy.orm import Session
from typing import List

from core.models import AcademicMember, ResearcherDetails, StudentDetails, MemberType
from database.session import get_session
from schemas import AcademicMemberCreate, AcademicMemberUpdate, AcademicMemberOut
from core.security import require_editor, get_current_user
from core.models import User

router = APIRouter(prefix="/members", tags=["Members"])

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@router.get("", response_model=List[AcademicMemberOut])
async def get_members(
    skip: int = 0,
    limit: int = 100,
    type: MemberType = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import joinedload
    query = db.query(AcademicMember).options(joinedload(AcademicMember.wps))
    if type:
        query = query.filter(AcademicMember.member_type == type)
    return query.offset(skip).limit(limit).all()

@router.post("", response_model=AcademicMemberOut)
async def create_member(
    member: AcademicMemberCreate,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    # Check if RUT or Email exists
    if member.rut and db.query(AcademicMember).filter(AcademicMember.rut == member.rut).first():
        raise HTTPException(status_code=400, detail="RUT already registered")
    if member.email and db.query(AcademicMember).filter(AcademicMember.email == member.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    db_member = AcademicMember(
        rut=member.rut,
        full_name=member.full_name,
        email=member.email,
        institution=member.institution,
        member_type=member.member_type,
        wp_id=member.wp_id,
        is_active=member.is_active
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)

    # Add details based on type
    if member.member_type == MemberType.RESEARCHER and member.researcher_details:
        details = ResearcherDetails(
            member_id=db_member.id,
            **member.researcher_details.dict()
        )
        db.add(details)
    elif member.member_type == MemberType.STUDENT and member.student_details:
        details = StudentDetails(
            member_id=db_member.id,
            **member.student_details.dict()
        )
        db.add(details)
    
    db.commit()
    db.refresh(db_member)
    return db_member

@router.post("/upload")
async def upload_documents(
    member_id: int = Form(...),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    member = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    if member.member_type != MemberType.STUDENT:
        raise HTTPException(status_code=400, detail="Only students can have documents")
        
    # Create directory if not exists
    upload_dir = f"uploads/students/{member_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = {}
    if member.student_details and member.student_details.document_paths:
        try:
            saved_paths = json.loads(member.student_details.document_paths)
        except:
            pass
            
    for file in files:
        file_path = f"{upload_dir}/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_paths[file.filename] = file_path
        
    if not member.student_details:
        member.student_details = StudentDetails(member_id=member.id)
        db.add(member.student_details)
        
    member.student_details.document_paths = json.dumps(saved_paths)
    db.commit()
    
    return {"message": "Files uploaded successfully", "paths": saved_paths}

@router.get("/{member_id}", response_model=AcademicMemberOut)
async def get_member(member_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member

@router.put("/{member_id}", response_model=AcademicMemberOut)
async def update_member(
    member_id: int,
    member_update: AcademicMemberUpdate,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    db_member = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Update basic fields
    update_data = member_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key not in ["researcher_details", "student_details"] and hasattr(db_member, key):
            setattr(db_member, key, value)

    # Update details
    if db_member.member_type == MemberType.RESEARCHER and member_update.researcher_details:
        if not db_member.researcher_details:
            db_member.researcher_details = ResearcherDetails(member_id=db_member.id)
        for key, value in member_update.researcher_details.dict(exclude_unset=True).items():
            setattr(db_member.researcher_details, key, value)
            
    elif db_member.member_type == MemberType.STUDENT and member_update.student_details:
        if not db_member.student_details:
            db_member.student_details = StudentDetails(member_id=db_member.id)
        for key, value in member_update.student_details.dict(exclude_unset=True).items():
            setattr(db_member.student_details, key, value)

    db.commit()
    db.refresh(db_member)
    return db_member

@router.delete("/{member_id}")
async def delete_member(
    member_id: int,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    db_member = db.query(AcademicMember).filter(AcademicMember.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    db.delete(db_member)
    db.commit()
    return {"message": "Member deleted successfully"}
