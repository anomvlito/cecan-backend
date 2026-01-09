#!/usr/bin/env python3
"""
Fix NaN values in academic_members table
Converts all NaN strings and numpy NaN to NULL
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def fix_nan_values():
    """Replace NaN strings with NULL in database"""
    db = SessionLocal()
    
    try:
        print("🔧 Fixing NaN values in academic_members...")
        
        # Update email NaN to NULL
        sql_email = text("""
        UPDATE academic_members 
        SET email = NULL 
        WHERE email = 'NaN' OR email = 'nan' OR email = '' OR UPPER(email) = 'NAN';
        """)
        
        result = db.execute(sql_email)
        db.commit()
        print(f"  ✅ Fixed {result.rowcount} email records")
        
        # Update RUT NaN to NULL
        sql_rut = text("""
        UPDATE academic_members 
        SET rut = NULL 
        WHERE rut = 'NaN' OR rut = 'nan' OR rut = '' OR UPPER(rut) = 'NAN';
        """)
        
        result = db.execute(sql_rut)
        db.commit()
        print(f"  ✅ Fixed {result.rowcount} RUT records")
        
        # Update institution NaN to NULL
        sql_inst = text("""
        UPDATE academic_members 
        SET institution = NULL 
        WHERE institution = 'NaN' OR institution = 'nan' OR institution = '' OR UPPER(institution) = 'NAN';
        """)
        
        result = db.execute(sql_inst)
        db.commit()
        print(f"  ✅ Fixed {result.rowcount} institution records")
        
        print("\n✅ All NaN values fixed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_nan_values()
