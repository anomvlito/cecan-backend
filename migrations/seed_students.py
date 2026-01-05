import pandas as pd
import os
import sys

# Add parent directory to path to allow importing 'core'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy.orm import Session
from database.session import get_db, engine
from core.models import Student, Thesis, StudentStatus, StudentProgram, ThesisStatus, AcademicMember
from difflib import get_close_matches

# --- Configuration ---
EXCEL_FILENAME = "Registro de estudiantes CECAN- Tabla actualizada 30 oct 2024.xlsx"
# Assuming script is in cecan-backend/migrations/
# We want to look in cecan-proyect/ (Root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXCEL_PATH = os.path.join(BASE_DIR, EXCEL_FILENAME)

def find_header_row(df_raw, keywords=["nombre", "alumno", "rut"]):
    """
    Scans the first 20 rows to find the header row based on keywords.
    Returns the dataframe re-read with the correct header.
    """
    print(f"🔍 Scanning for headers matching: {keywords}")
    for i, row in df_raw.head(20).iterrows():
        # Convert row to string and check if it contains keywords
        row_str = row.astype(str).str.lower().tolist()
        matches = sum(1 for k in keywords if any(k in str(x) for x in row_str))
        
        if matches >= 2: # At least 2 keywords match
            print(f"✅ Header found at row {i}")
            # Re-read the file skipping previous rows
            # Note: We can't easily re-read from the df object, so we filter.
            # A better way is to set columns
            df_new = df_raw.iloc[i+1:].copy()
            df_new.columns = df_raw.iloc[i]
            return df_new
            
    print("⚠️ Header not found dynamically. Assuming Row 0.")
    return df_raw

def normalize_status(status_str):
    if not isinstance(status_str, str): return StudentStatus.ACTIVE # Default
    s = status_str.lower().strip()
    if "graduado" in s or "titulado" in s: return StudentStatus.GRADUATED
    if "retirado" in s or "baja" in s: return StudentStatus.WITHDRAWN
    if "suspendido" in s: return StudentStatus.SUSPENDED
    return StudentStatus.ACTIVE

def normalize_program(prog_str):
    if not isinstance(prog_str, str): return StudentProgram.OTHER
    p = prog_str.lower().strip()
    if "doct" in p or "phd" in p: return StudentProgram.DOCTORADO
    if "mag" in p or "m.sc" in p or "maest" in p: return StudentProgram.MAGISTER
    if "post" in p: return StudentProgram.POSTDOC
    return StudentProgram.OTHER

def clean_date(val):
    if pd.isna(val): return None
    if isinstance(val, datetime): return val
    # Try parsing string formats if needed
    return None

def seed_students():
    print(f"🚀 Starting Student Import from: {EXCEL_FILENAME}")
    
    # 1. Load Excel
    try:
        # Read without header first to find it dynamically
        df_raw = pd.read_excel(EXCEL_PATH, header=None)
        df = find_header_row(df_raw)
    except FileNotFoundError:
        print(f"❌ File not found: {EXCEL_PATH}")
        return

    # 2. Normalize Column Names
    df.columns = df.columns.astype(str).str.strip().str.lower()
    print("Found columns:", list(df.columns))

    # Map columns explicitly (Adjust these based on actual Excel headers)
    # Expected: "nombre", "rut", "universidad", "programa", "tutor", "tesis", "situacion"
    # We iterate and find best match
    
    col_map = {
        "full_name": ["nombre", "alumno", "estudiante"],
        "rut": ["rut", "identidad"],
        "uni": ["universidad", "institucion"],
        "prog": ["programa", "grado"],
        "tutor": ["tutor", "profesor guia"],
        "thesis": ["tesis", "titulo tesis"],
        "status": ["situacion", "estado"]
    }

    final_cols = {}
    for key, candidates in col_map.items():
        found = False
        for c in df.columns:
            if any(cand in c for cand in candidates):
                final_cols[key] = c
                found = True
                break
        if not found:
            print(f"⚠️ Warning: Could not find column for '{key}'")

    db = next(get_db())
    count = 0
    
    # Pre-fetch tutors for matching
    tutors = db.query(AcademicMember).all()
    tutor_names = {t.full_name.lower(): t.id for t in tutors}
    
    for idx, row in df.iterrows():
        # Extrac Data
        full_name = row.get(final_cols.get("full_name"), "Desconocido")
        if pd.isna(full_name) or str(full_name).strip() == "": continue
        
        rut = str(row.get(final_cols.get("rut"), "")).strip()
        uni = str(row.get(final_cols.get("uni"), "")).strip()
        
        prog_raw = str(row.get(final_cols.get("prog"), ""))
        program = normalize_program(prog_raw)
        
        status_raw = str(row.get(final_cols.get("status"), ""))
        status = normalize_status(status_raw)
        
        # Tutor Matching
        tutor_raw = str(row.get(final_cols.get("tutor"), "")).lower().strip()
        tutor_id = None
        # Simple exact substring match or naive fuzzy
        best_match = get_close_matches(tutor_raw, tutor_names.keys(), n=1, cutoff=0.6)
        if best_match:
            tutor_id = tutor_names[best_match[0]]
            # print(f"   Matched Tutor: '{tutor_raw}' -> {best_match[0]}")

        # Create Student
        student = Student(
            full_name=full_name,
            rut=rut if len(rut) > 2 else None,
            university=uni,
            program=program,
            status=status,
            tutor_id=tutor_id
        )
        db.add(student)
        db.flush() # Get ID
        
        # Create Thesis (if title exists)
        thesis_title = str(row.get(final_cols.get("thesis"), ""))
        if len(thesis_title) > 5 and "nan" not in thesis_title.lower():
            thesis = Thesis(
                title=thesis_title,
                student_id=student.id,
                status=ThesisStatus.PROPOSAL if status == StudentStatus.ACTIVE else ThesisStatus.APPROVED
            )
            db.add(thesis)
            
        count += 1

    db.commit()
    print(f"✅ Imported {count} students successfully!")

if __name__ == "__main__":
    seed_students()
