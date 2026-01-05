from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from database.session import get_db
from core.models import User, UserRole
from core.security import get_current_user, require_editor, require_admin
from schemas import StudentOut, StudentCreate, StudentUpdate, ThesisCreate, ThesisOut, ThesisUpdate
from services.student_service import StudentService

router = APIRouter(prefix="/students", tags=["students"])

@router.get("/", response_model=List[StudentOut])
def list_students(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all students with their theses, paginated."""
    return StudentService.get_students(db, skip, limit)

@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Get a specific student by ID."""
    student = StudentService.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.post("/", response_model=StudentOut)
def create_student(
    student: StudentCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """Create a new student (Editor only)."""
    return StudentService.create_student(db, student)

@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    student: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """Update student details."""
    updated = StudentService.update_student(db, student_id, student)
    if not updated:
         raise HTTPException(status_code=404, detail="Student not found")
    return updated

@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a student and their theses (Admin only)."""
    success = StudentService.delete_student(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": "success", "message": "Student deleted"}

# --- Thesis Sub-resources ---

@router.post("/{student_id}/theses", response_model=ThesisOut)
def add_thesis(
    student_id: int,
    thesis: ThesisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_editor)
):
    """Add a thesis to a student."""
    if thesis.student_id != student_id:
        raise HTTPException(status_code=400, detail="Student ID mismatch")
    
    # Verify student exists
    if not StudentService.get_student(db, student_id):
        raise HTTPException(status_code=404, detail="Student not found")
        
    return StudentService.add_thesis(db, thesis)
