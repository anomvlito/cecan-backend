import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("=== Auditoría de Vínculos Alumno-Tutor ===")
    
    # 1. Cantidad de alumnos con y sin tutor_id
    res = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(tutor_id) as with_tutor,
            COUNT(*) - COUNT(tutor_id) as without_tutor
        FROM students
    """)).fetchone()
    print(f"Total Estudiantes: {res.total}")
    print(f"Con Tutor ID: {res.with_tutor}")
    print(f"Sin Tutor ID: {res.without_tutor}")
    
    # 2. Muestra de alumnos y sus tutores vinculados
    print("\nSample de vínculos (Estudiante -> Tutor):")
    samples = db.execute(text("""
        SELECT s.full_name as student, m.full_name as tutor
        FROM students s
        LEFT JOIN academic_members m ON s.tutor_id = m.id
        WHERE s.tutor_id IS NOT NULL
        LIMIT 10
    """)).fetchall()
    for s in samples:
        print(f"  🎓 {s[0]} -> 👨‍🏫 {s[1]}")
        
    # 3. Investigadores disponibles en academic_members
    researcher_count = db.execute(text("SELECT COUNT(*) FROM academic_members WHERE member_type = 'researcher'")).scalar()
    print(f"\nTotal Investigadores en DB: {researcher_count}")
    
finally:
    db.close()
