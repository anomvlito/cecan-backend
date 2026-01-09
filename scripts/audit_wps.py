#!/usr/bin/env python3
"""
Audit and clean invalid WPs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def audit_and_clean_wps():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("🔍 Auditing Work Packages")
        print("=" * 80)
        
        # Check what WPs exist in work_packages table
        sql = text("SELECT id, name FROM work_packages ORDER BY id;")
        wps = db.execute(sql).fetchall()
        
        print(f"\n📊 Work Packages en la tabla work_packages:")
        for wp in wps:
            print(f"   WP {wp.id}: {wp.name}")
        
        valid_wp_ids = [wp.id for wp in wps if wp.id <= 5]  # Only 1-5 are valid
        
        print(f"\n✅ WPs válidos: {valid_wp_ids}")
        
        # Count researchers with invalid WPs
        sql = text("""
            SELECT COUNT(*) 
            FROM academic_members 
            WHERE member_type = 'researcher' 
              AND is_active = TRUE
              AND wp_id > 5;
        """)
        invalid_count = db.execute(sql).scalar()
        
        print(f"\n⚠️  Investigadores activos con WP inválido (>5): {invalid_count}")
        
        if invalid_count > 0:
            # Show researchers with invalid WPs
            sql = text("""
                SELECT id, full_name, wp_id
                FROM academic_members
                WHERE member_type = 'researcher'
                  AND is_active = TRUE
                  AND wp_id > 5
                ORDER BY wp_id, full_name
                LIMIT 20;
            """)
            researchers = db.execute(sql).fetchall()
            
            print(f"\n📋 Primeros 20 investigadores con WP inválido:")
            for r in researchers:
                print(f"   {r.id:<5} {r.full_name:<40} WP {r.wp_id}")
            
            # Ask for confirmation to clean
            print(f"\n🧹 Opciones:")
            print(f"   1. Poner wp_id = NULL para investigadores con WP > 5")
            print(f"   2. Borrar WPs > 5 de la tabla work_packages (si existen)")
            print(f"\n   Para ejecutar, modifica el script y descomenta las líneas de limpieza.")
            
            # UNCOMMENT TO CLEAN:
            # print(f"\n🧹 Limpiando wp_id inválidos...")
            # sql = text("""
            #     UPDATE academic_members
            #     SET wp_id = NULL
            #     WHERE wp_id > 5;
            # """)
            # db.execute(sql)
            # db.commit()
            # print(f"   ✅ WP inválidos limpiados")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    audit_and_clean_wps()
