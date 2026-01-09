import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Relación entre tablas de Alumnos ===")
    
    # 1. Conteo en academic_members (tipo student)
    am_count = db.execute(text("SELECT COUNT(*) FROM academic_members WHERE member_type = 'student'")).scalar()
    print(f"AcademicMembers (estudiantes): {am_count}")
    
    # 2. Conteo en student_details
    sd_count = db.execute(text("SELECT COUNT(*) FROM student_details")).scalar()
    print(f"StudentDetails: {sd_count}")
    
    # 3. Conteo en la tabla 'students' (la que usa el front ahora)
    s_count = db.execute(text("SELECT COUNT(*) FROM students")).scalar()
    print(f"Students table (standalone): {s_count}")
    
    # 4. Ver si los nombres coinciden
    print("\nNombres en 'students' vs 'academic_members':")
    res = db.execute(text("""
        SELECT s.full_name as s_name, am.full_name as am_name
        FROM students s
        LEFT JOIN academic_members am ON s.full_name = am.full_name AND am.member_type = 'student'
        LIMIT 5
    """)).fetchall()
    for row in res:
        print(f"  Students Table: {row[0]} | AcademicMember match: {row[1]}")

    # 5. Ver contenido de student_details para un member_id
    print("\nDetalles en student_details:")
    res = db.execute(text("""
        SELECT sd.member_id, am.full_name, sd.program, sd.tutor_id
        FROM student_details sd
        JOIN academic_members am ON sd.member_id = am.id
        LIMIT 5
    """)).fetchall()
    for row in res:
        print(f"  ID: {row[0]} | Name: {row[1]} | Program: {row[2]} | TutorID: {row[3]}")

finally:
    db.close()
