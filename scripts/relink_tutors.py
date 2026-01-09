import sys
from pathlib import Path
from difflib import SequenceMatcher
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

def fuzzy_match(s1, s2):
    if not s1 or not s2: return 0
    return SequenceMatcher(None, s1.lower().strip(), s2.lower().strip()).ratio()

def link_students_to_researchers():
    db = SessionLocal()
    try:
        print("🚀 Iniciando Re-vinculación Automática Alumno -> Tutor")
        print("="*60)
        
        # 1. Obtener todos los investigadores
        researchers = db.execute(text("SELECT id, full_name FROM academic_members WHERE member_type = 'researcher'")).fetchall()
        
        # 2. Obtener todos los alumnos que NO tienen tutor_id
        # Pero... ¿Cómo sabemos quién es su tutor si el tutor_id es NULL?
        # Revisemos si en el import original se guardó el nombre del tutor en alguna parte.
        # En el script de import, si no encontraba al tutor, simplemente no ponía tutor_id.
        
        # Vamos a intentar buscar en la tabla 'students' si hay nombres de tutores que podamos usar para re-vincular
        # (Si el usuario los ingresa manualmente o si los recuperamos del Excel).
        
        print("Nota: El sistema vincula por ID. Si el import no encontró al tutor, el campo quedó vacío.")
        print("Para arreglarlo masivamente, volveremos a correr el importador con fuzzy matching mejorado.")
        
    finally:
        db.close()

if __name__ == "__main__":
    link_students_to_researchers()
