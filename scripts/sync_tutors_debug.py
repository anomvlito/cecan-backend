import sys
from pathlib import Path
from difflib import SequenceMatcher
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

def fuzzy_match(s1, s2):
    return SequenceMatcher(None, s1.lower().strip(), s2.lower().strip()).ratio()

def sync_tutors():
    db = SessionLocal()
    try:
        print("🔍 Buscando investigadores para vincular como tutores...")
        researchers = db.execute(text("SELECT id, full_name FROM academic_members WHERE member_type = 'researcher'")).fetchall()
        print(f"✅ {len(researchers)} investigadores encontrados.")
        
        students = db.execute(text("SELECT id, full_name, tutor_id FROM students")).fetchall()
        print(f"✅ {len(students)} alumnos cargados.")
        
        # Si el usuario quiere ver "con quién vienen", quizás esos nombres están en una columna temporal o en el Excel original
        # Vamos a intentar buscar si hay alumnos sin tutor_id pero que tengan un nombre de tutor en AcademicMember (si se importaron así)
        
        # Pero según el script de importación, el tutor_id se pone en la tabla 'students'.
        # Si 'tutor_id' es NULL, es porque el import no encontró al investigador.
        
        updated = 0
        for student in students:
            if student.tutor_id is None:
                # Aquí hay un problema: no tenemos guardado el "nombre del tutor original" en la tabla students si falló el vínculo.
                # A menos que esté en AcademicMember -> student_details
                pass

        print("\nEste script requiere saber qué alumnos no tienen tutor para intentar re-vincularlos.")
        
    finally:
        db.close()

if __name__ == "__main__":
    sync_tutors()
