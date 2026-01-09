import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    members = db.execute(text("SELECT COUNT(*) FROM academic_members")).scalar()
    students_table = db.execute(text("SELECT COUNT(*) FROM students")).scalar()
    student_details_table = db.execute(text("SELECT COUNT(*) FROM student_details")).scalar()
    
    print(f"Members: {members}")
    print(f"Students table: {students_table}")
    print(f"StudentDetails table: {student_details_table}")
    
    # Check sample from students table
    res = db.execute(text("SELECT full_name FROM students LIMIT 5")).fetchall()
    print("Sample from students table:", [r[0] for r in res])
    
    # Check sample from academic_members (students)
    res = db.execute(text("SELECT full_name FROM academic_members WHERE member_type='student' LIMIT 5")).fetchall()
    print("Sample from academic_members (students):", [r[0] for r in res])
finally:
    db.close()
