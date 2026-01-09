import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

def unify_students():
    db = SessionLocal()
    try:
        print("🧹 Iniciando UNIFICACIÓN de datos de alumnos...")
        
        # 1. Limpiar tabla 'students' standalone (los 66 registros, muchos parecen basura)
        print("Truncando tabla 'students'...")
        db.execute(text("TRUNCATE TABLE students CASCADE"))
        
        # 2. Reiniciar secuencia de ID si es necesario (Postgres)
        try:
            db.execute(text("ALTER SEQUENCE students_id_seq RESTART WITH 1"))
        except:
            pass

        # 3. Obtener los alumnos reales de academic_members + student_details
        print("Obteniendo alumnos de 'academic_members' y 'student_details'...")
        alumnos_ricos = db.execute(text("""
            SELECT 
                am.full_name, am.email, am.rut, 
                sd.program, sd.university, sd.program_start as start_date, sd.defense_date as graduation_date,
                sd.tutor_id, sd.co_tutor_id,
                am.wp_id -- Asumimos que am tiene el wp_id
            FROM academic_members am
            JOIN student_details sd ON am.id = sd.member_id
            WHERE am.member_type = 'student'
        """)).fetchall()
        
        print(f"Encontrados {len(alumnos_ricos)} alumnos reales.")
        
        # 4. Insertar en la tabla 'students'
        for row in alumnos_ricos:
            # Obtener nombres de tutores por ID para persistir el texto
            t_name = None
            if row.tutor_id:
                t_name = db.execute(text("SELECT full_name FROM academic_members WHERE id = :id"), {"id": row.tutor_id}).scalar()
            
            ct_name = None
            if row.co_tutor_id:
                ct_name = db.execute(text("SELECT full_name FROM academic_members WHERE id = :id"), {"id": row.co_tutor_id}).scalar()

            db.execute(text("""
                INSERT INTO students (
                    full_name, email, rut, program, university, 
                    start_date, graduation_date, status, 
                    tutor_id, co_tutor_id, tutor_name, co_tutor_name, wp_id
                ) VALUES (
                    :name, :email, :rut, :prog, :uni, 
                    :start, :grad, 'Activo', 
                    :t_id, :ct_id, :t_name, :ct_name, :wp_id
                )
            """), {
                "name": row.full_name,
                "email": row.email,
                "rut": row.rut,
                "prog": row.program,
                "uni": row.university,
                "start": row.start_date,
                "grad": row.graduation_date,
                "t_id": row.tutor_id,
                "ct_id": row.co_tutor_id,
                "t_name": t_name,
                "ct_name": ct_name,
                "wp_id": row.wp_id
            })
        
        db.commit()
        print(f"✅ Unificación completada. {len(alumnos_ricos)} alumnos migrados a la tabla principal.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    unify_students()
