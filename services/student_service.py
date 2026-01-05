from sqlalchemy.orm import Session, joinedload
from core.models import Student, Thesis, StudentStatus, ThesisStatus, AcademicMember
from schemas import StudentCreate, StudentUpdate, ThesisCreate, ThesisUpdate
from typing import List, Optional
from datetime import datetime

class StudentService:
    @staticmethod
    def get_students(db: Session, skip: int = 0, limit: int = 100) -> List[Student]:
        # Join with tutor to be efficient? 
        # But for list view we might just need names. 
        # Using joinedload for tutor and theses.
        return db.query(Student).options(
            joinedload(Student.tutor),
            joinedload(Student.co_tutor),
            joinedload(Student.theses)
        ).offset(skip).limit(limit).all()

    @staticmethod
    def get_student(db: Session, student_id: int) -> Optional[Student]:
        return db.query(Student).options(
            joinedload(Student.tutor),
            joinedload(Student.co_tutor),
            joinedload(Student.theses)
        ).filter(Student.id == student_id).first()

    @staticmethod
    def create_student(db: Session, student_in: StudentCreate) -> Student:
        db_student = Student(**student_in.dict())
        db.add(db_student)
        db.commit()
        db.refresh(db_student)
        return db_student

    @staticmethod
    def update_student(db: Session, student_id: int, student_in: StudentUpdate) -> Optional[Student]:
        db_student = db.query(Student).filter(Student.id == student_id).first()
        if not db_student:
            return None
        
        update_data = student_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_student, key, value)
            
        db.commit()
        db.refresh(db_student)
        return db_student
    
    @staticmethod
    def delete_student(db: Session, student_id: int) -> bool:
        db_student = db.query(Student).filter(Student.id == student_id).first()
        if not db_student:
            return False
        db.delete(db_student)
        db.commit()
        return True

    # --- Thesis Logic ---
    @staticmethod
    def add_thesis(db: Session, thesis_in: ThesisCreate) -> Thesis:
        db_thesis = Thesis(**thesis_in.dict())
        # Check student exists ? Constraint handles it.
        db.add(db_thesis)
        db.commit()
        db.refresh(db_thesis)
        return db_thesis
    
    @staticmethod
    def update_thesis(db: Session, thesis_id: int, thesis_in: ThesisUpdate) -> Optional[Thesis]:
        db_thesis = db.query(Thesis).filter(Thesis.id == thesis_id).first()
        if not db_thesis:
            return None
            
        update_data = thesis_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_thesis, key, value)
            
        db.commit()
        db.refresh(db_thesis)
        return db_thesis
