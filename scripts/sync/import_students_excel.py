
import os
import sys
import pandas as pd
from sqlalchemy.orm import Session
from difflib import get_close_matches

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import get_session
from core.models import Student, Thesis, AcademicMember, StudentProgram, StudentStatus, ThesisStatus

def find_file(filename):
    # Try different locations
    locations = [
        filename,
        os.path.join("..", filename),
        os.path.join("..", "..", filename),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", filename)
    ]
    for loc in locations:
        if os.path.exists(loc):
            return loc
    return None

def normalize_text(text):
    if pd.isna(text) or not isinstance(text, str):
        return ""
    return str(text).strip()

def find_member_by_name(db: Session, name_query):
    if not name_query:
        return None
    
    name_query = name_query.strip()
    # 1. Exact match
    member = db.query(AcademicMember).filter(AcademicMember.full_name.ilike(f"%{name_query}%")).first()
    if member:
        return member
        
    # 2. Fuzzy match (simplified)
    all_names = [m.full_name for m in db.query(AcademicMember).all()]
    matches = get_close_matches(name_query, all_names, n=1, cutoff=0.6)
    if matches:
        return db.query(AcademicMember).filter(AcademicMember.full_name == matches[0]).first()
    
    return None


def clean_rut(rut_str):
    if pd.isna(rut_str):
        return None
    
    # Normalize
    cleaned = str(rut_str).strip().upper()
    
    # Remove common clutter
    cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(" (PASAPORTE)", "")
    cleaned = cleaned.replace("(PASAPORTE)", "")
    
    # Formatting basics
    # If it has dots, they are removed.
    # If it is a standard RUT (e.g. 11222333-K), it stays 11222333-K
    
    return cleaned[:20] # Final safety clip, but cleaning should make it fit

def import_students():
    filename = "Registro de estudiantes CECAN- Tabla actualizada 30 oct 2024.xlsx"
    file_path = find_file(filename)
    
    if not file_path:
        print(f"Error: Could not find '{filename}'")
        return

    print(f"Loading {file_path}...")
    try:
        # Step 1: Detect Header Row
        # Read the first 20 rows without header
        df_scan = pd.read_excel(file_path, header=None, nrows=20)
        
        header_row_idx = None
        for idx, row in df_scan.iterrows():
            # Convert row to string and check for keywords
            row_str = " ".join([str(val).lower() for val in row.values])
            
            # Keywords that must appear in the header
            if "nombre" in row_str and ("programa" in row_str or "institución" in row_str or "universidad" in row_str):
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            print("Warning: Could not detect header row automatically. Trying default (0).")
            header_row_idx = 0
        else:
            print(f"✅ Auto-detected header at row index: {header_row_idx}")

        # Step 2: Read Data with identifying header
        df = pd.read_excel(file_path, header=header_row_idx)

    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]
    print("Columns found:", df.columns.tolist())
    
    # Map columns to internal keys
    col_map = {}
    for col in df.columns:
        c = col.lower()
        if "nombre" in c and "estudiante" in c: col_map["name"] = col
        elif "nombre" in c and "name" not in col_map: col_map["name"] = col # Fallback
        elif "mail" in c or "correo" in c: col_map["email"] = col
        elif "rut" in c: col_map["rut"] = col
        elif "programa" in c: col_map["program"] = col
        elif "universidad" in c or "institución" in c: col_map["university"] = col
        elif ("tutor" in c or "guía" in c) and "co" not in c: col_map["tutor"] = col
        elif "cotutor" in c or "co-guía" in c or "co-tutor" in c: col_map["cotutor"] = col
        elif "tesis" in c or "tema" in c: col_map["thesis"] = col
        elif "estado" in c: col_map["status"] = col

    print("Column Mapping:", col_map)
    
    if "name" not in col_map:
        print("Error: Could not identify Student Name column even after detection.")
        return

    db = get_session()
    
    processed = 0
    created = 0
    
    for idx, row in df.iterrows():
        name = normalize_text(row.get(col_map.get("name")))
        if not name or name.lower() in ["nan", "none", ""]:
            continue
            
        # Skip if name looks like a header repetition or junk
        if "nombre" in name.lower() and "estudiante" in name.lower():
            continue

        print(f"Processing: {name}")
        processed += 1
        
        # Check if exists
        student = db.query(Student).filter(Student.full_name == name).first()
        if not student:
            student = Student(full_name=name)
            created += 1
            db.add(student)
            
        # Update fields
        if "email" in col_map: 
            val = normalize_text(row.get(col_map["email"]))
            if val: student.email = val
            
        if "rut" in col_map: 
            raw_rut = row.get(col_map["rut"])
            cleaned_rut = clean_rut(raw_rut)
            if cleaned_rut: 
                student.rut = cleaned_rut

            
        if "university" in col_map: 
            val = normalize_text(row.get(col_map["university"]))
            if val: student.university = val
        
        # Program handling
        raw_program = normalize_text(row.get(col_map.get("program")))
        if "doctorado" in raw_program.lower():
            student.program = StudentProgram.DOCTORADO
        elif "magíster" in raw_program.lower() or "magister" in raw_program.lower():
            student.program = StudentProgram.MAGISTER
        elif "postdoc" in raw_program.lower():
            student.program = StudentProgram.POSTDOC
        else:
            student.program = StudentProgram.OTHER

        # Status
        # Default active
        
        # Tutors
        if "tutor" in col_map:
            tutor_name = normalize_text(row.get(col_map["tutor"]))
            if tutor_name and tutor_name.lower() not in ["no apply", "n/a", "-"]:
                tutor = find_member_by_name(db, tutor_name)
                if tutor:
                    student.tutor = tutor
                    print(f"  -> Assigned Tutor: {tutor.full_name}")
                else:
                    print(f"  -> Tutor not found/matched: {tutor_name}")

        if "cotutor" in col_map:
            cotutor_name = normalize_text(row.get(col_map["cotutor"]))
            if cotutor_name and cotutor_name.lower() not in ["no apply", "n/a", "-"]:
                cotutor = find_member_by_name(db, cotutor_name)
                if cotutor:
                    student.co_tutor = cotutor
                    print(f"  -> Assigned Co-Tutor: {cotutor.full_name}")

        db.commit() # Commit student to get ID
        
        # Thesis
        if "thesis" in col_map:
            thesis_title = normalize_text(row.get(col_map["thesis"]))
            if thesis_title and len(thesis_title) > 3:
                # Check if thesis exists
                thesis = db.query(Thesis).filter(Thesis.student_id == student.id).first()
                if not thesis:
                    thesis = Thesis(
                        title=thesis_title,
                        student_id=student.id,
                        status=ThesisStatus.PROPOSAL # Default
                    )
                    db.add(thesis)
                    print(f"  -> Created Thesis: {thesis_title[:30]}...")
                else:
                    if thesis.title != thesis_title:
                        thesis.title = thesis_title # Update title if changed
        
    db.commit()
    print(f"Done. Processed {processed} students. Created {created} new entries.")

if __name__ == "__main__":
    import_students()
