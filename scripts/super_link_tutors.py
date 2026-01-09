#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
import re
from pathlib import Path
from difflib import SequenceMatcher
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.session import SessionLocal
from sqlalchemy import text

INPUT_FILE = "data/cecan_personnel_normalized.xlsx"

def clean_name(name):
    if not name or pd.isna(name): return ""
    # Quitar cosas entre paréntesis como (wp4)
    name = re.sub(r'\(.*?\)', '', str(name))
    return name.strip()

def fuzzy_match(s1, s2):
    s1 = clean_name(s1).lower()
    s2 = clean_name(s2).lower()
    return SequenceMatcher(None, s1, s2).ratio()

def super_link_tutors():
    db = SessionLocal()
    try:
        print("\n🚀 INICIANDO VINCULACIÓN INTELIGENTE ALUMNO -> TUTOR")
        print("="*70)
        
        # 1. Cargar Investigadores de la base de datos
        researchers = db.execute(text("SELECT id, full_name FROM academic_members WHERE member_type = 'researcher'")).fetchall()
        print(f"✅ {len(researchers)} investigadores disponibles para vincular.")
        
        # 2. Leer Excel
        print(f"📖 Leyendo datos desde: {INPUT_FILE}")
        df = pd.read_excel(INPUT_FILE, sheet_name='students')
        
        linked_count = 0
        
        for _, row in df.iterrows():
            st_name = str(row['full_name']).strip()
            t_raw = str(row.get('tutor_name'))
            
            # Caso especial: Si hay una barra '/', tomamos el primero como tutor y el segundo como co-tutor
            t_orig = t_raw
            ct_orig = str(row.get('co_tutor_name'))
            
            if '/' in t_raw:
                parts = t_raw.split('/')
                t_orig = parts[0].strip()
                if ct_orig == 'nan' or not ct_orig:
                    ct_orig = parts[1].strip()

            t_orig = clean_name(t_orig)
            ct_orig = clean_name(ct_orig)
            
            if not t_orig or t_orig.lower() in ['nan', 'none', '']: continue
            
            # Buscar mejor match para Tutor
            best_t_id, best_t_score, best_t_name = None, 0, ""
            for rid, rname in researchers:
                score = fuzzy_match(t_orig, rname)
                # Si no hay match perfecto, intentamos ver si el nombre del tutor está contenido en el del investigador
                if score < 0.8 and t_orig.lower() in rname.lower():
                    score = 0.85 
                
                if score > best_t_score:
                    best_t_score, best_t_id, best_t_name = score, rid, rname
            
            # Buscar mejor match para Co-Tutor
            best_ct_id, best_ct_score, best_ct_name = None, 0, ""
            if ct_orig and ct_orig.lower() not in ['nan', 'none', '']:
                for rid, rname in researchers:
                    score = fuzzy_match(ct_orig, rname)
                    if score > best_ct_score:
                        best_ct_score, best_ct_id, best_ct_name = score, rid, rname

            # Si el match es bueno (> 80% similitud)
            if best_t_score > 0.8:
                # Actualizar tutor principal
                db.execute(text("""
                    UPDATE students SET tutor_id = :tid WHERE full_name = :sname
                """), {"tid": best_t_id, "sname": st_name})
                
                # Actualizar también student_details por si acaso
                m_id = db.execute(text("SELECT id FROM academic_members WHERE full_name = :sname AND member_type = 'student'"), {"sname": st_name}).scalar()
                if m_id:
                    db.execute(text("""
                        UPDATE student_details SET tutor_id = :tid WHERE member_id = :mid
                    """), {"tid": best_t_id, "mid": m_id})

                # Vincular Co-Tutor si el match es bueno
                if best_ct_id and best_ct_score > 0.8:
                    db.execute(text("UPDATE students SET co_tutor_id = :ctid WHERE full_name = :sname"), {"ctid": best_ct_id, "sname": st_name})
                    if m_id:
                        db.execute(text("UPDATE student_details SET co_tutor_id = :ctid WHERE member_id = :mid"), {"ctid": best_ct_id, "mid": m_id})
                
                print(f"🔗 {st_name[:20]:<20} -> Tutor: {best_t_name[:25]:<25} ({int(best_t_score*100)}%)")
                linked_count += 1
            else:
                print(f"⚠️ {st_name[:20]:<20} -> Sin match para '{t_orig}'")
        
        db.commit()
        print("\n" + "="*70)
        print(f"📊 RESULTADO: {linked_count} alumnos vinculados correctamente.")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    super_link_tutors()
