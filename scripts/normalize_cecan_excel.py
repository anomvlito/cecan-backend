#!/usr/bin/env python3
"""
Normalize CECAN Excel
Reads 5 sheets, cleans data, exports 2 normalized sheets
"""
import pandas as pd
import re
from pathlib import Path

INPUT_FILE = "data/Base Investigadores CECAN rev ccv- 20 nov 2025.xlsx"
OUTPUT_FILE = "data/cecan_personnel_normalized.xlsx"

def clean_email(email_str):
    """Extract first valid email from malformed string"""
    if pd.isna(email_str) or not email_str:
        return None
    
    email_str = str(email_str).strip()
    
    # Handle multiple emails separated by ; or /
    if ';' in email_str or '/' in email_str:
        parts = re.split(r'[;/\s]+', email_str)
        for part in parts:
            part = part.strip()
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', part):
                return part.lower()
    
    # Return if valid
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
        return email_str.lower()
    
    return None

def clean_rut(rut_str):
    """Clean RUT format"""
    if pd.isna(rut_str):
        return None
    return str(rut_str).strip()

def clean_name(name):
    """Clean and normalize name"""
    if pd.isna(name):
        return ""
    return str(name).strip()

def normalize_personnel():
    """Consolidate investigators and staff into single sheet"""
    print("=" * 80)
    print("🔄 Normalizing Personnel Data")
    print("=" * 80)
    
    all_personnel = []
    
    # Process each type of investigator
    sheets_config = [
        ("INV. PRINCIPAL", "researcher", "Principal"),
        ("INV. ASOCIADOS", "researcher", "Asociado"),
        ("INV. ADJUNTOS", "researcher", "Adjunto"),
        ("PERSONAL DE APOYO", "staff", None),
    ]
    
    for sheet_name, member_type, category in sheets_config:
        print(f"\n📄 Processing: {sheet_name}")
        df = pd.read_excel(INPUT_FILE, sheet_name=sheet_name)
        print(f"   Total rows in sheet: {len(df)}")
        
        count = 0
        for idx, row in df.iterrows():
            full_name = f"{clean_name(row.get('NOMBRE', ''))} {clean_name(row.get('APELLIDO PATERNO', ''))} {clean_name(row.get('APELLIDO MATERNO', ''))}".strip()
            
            if not full_name or full_name == "":
                print(f"   ⚠️  Row {idx+1}: Skipped (no name)")
                continue
            
            person = {
                "full_name": full_name,
                "email": clean_email(row.get("EMAIL")),
                "rut": clean_rut(row.get("RUT")),
                "wp": str(row.get("WP", "")).strip() if not pd.isna(row.get("WP")) else None,
                "member_type": member_type,
                "category": category,
                "institution": clean_name(row.get("EMPRESA", "")),
                "phone": clean_name(row.get("TELÉFONO/CEL", "")),
                "cargo": clean_name(row.get("CARGO", "")),
                "is_active": True
            }
            
            all_personnel.append(person)
            count += 1
            print(f"   [{count}/{len(df)}] ✅ {full_name}")
        
        print(f"   ✅ Processed {count} records from {sheet_name}")
    
    df_personnel = pd.DataFrame(all_personnel)
    print(f"\n📊 Total Personnel Consolidated: {len(df_personnel)}")
    return df_personnel

def normalize_students():
    """Process students sheet"""
    print("\n" + "=" * 80)
    print("🎓 Normalizing Students Data")
    print("=" * 80)
    
    df = pd.read_excel(INPUT_FILE, sheet_name="ALUMNOS")
    print(f"   Total rows in sheet: {len(df)}")
    
    students = []
    count = 0
    
    for idx, row in df.iterrows():
        full_name = f"{clean_name(row.get('Nombres', ''))} {clean_name(row.get('Paterno', ''))} {clean_name(row.get('Materno', ''))}".strip()
        
        if not full_name:
            print(f"   ⚠️  Row {idx+1}: Skipped (no name)")
            continue
        
        student = {
            "full_name": full_name,
            "email": clean_email(row.get("Email")),
            "rut": clean_rut(row.get("RUT")),
            "wp": str(row.get("WP", "")).strip() if not pd.isna(row.get("WP")) else None,
            "member_type": "student",
            "tutor_name": clean_name(row.get("Director de tesis", "")),
            "co_tutor_name": clean_name(row.get("Co-Tutor", "")),
            "thesis_title": clean_name(row.get("Título de tesis", "")),
            "program": clean_name(row.get("Programa", "")),
            "university": clean_name(row.get("Universidad", "")),
            "degree_type": clean_name(row.get("Tipo de grado", "")),
            "is_active": True
        }
        
        students.append(student)
        count += 1
        print(f"   [{count}/{len(df)}] ✅ {full_name} (Tutor: {student['tutor_name']})")
    
    df_students = pd.DataFrame(students)
    print(f"\n📊 Total Students Processed: {len(df_students)}")
    return df_students

def main():
    print("\n🚀 CECAN Excel Normalization Script")
    print("=" * 80)
    
    # Step 1: Normalize personnel
    df_personnel = normalize_personnel()
    
    # Step 2: Normalize students
    df_students = normalize_students()
    
    # Step 3: Export to Excel
    print("\n" + "=" * 80)
    print(f"💾 Exporting to: {OUTPUT_FILE}")
    print("=" * 80)
    
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        df_personnel.to_excel(writer, sheet_name='personnel', index=False)
        df_students.to_excel(writer, sheet_name='students', index=False)
    
    print(f"\n✅ Normalization complete!")
    print(f"   Personnel: {len(df_personnel)} rows")
    print(f"   Students: {len(df_students)} rows")
    print(f"\n📂 File saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
