#!/usr/bin/env python3
"""
Remap invalid WPs to correct ones
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import SessionLocal
from sqlalchemy import text

def remap_wps():
    db = SessionLocal()
    
    # Mapping of incorrect WP IDs to correct ones
    wp_mapping = {
        6: 1,   # WP1 → Prevención
        11: 1,  # WP1.0 → Prevención
        7: 2,   # WP2 → Optimización
        12: 2,  # WP2.0 → Optimización
        8: 3,   # WP3 → Innovación
        13: 3,  # WP3.0 → Innovación
        16: 3,  # WP3-4 → Innovación (asumimos WP3)
        9: 4,   # WP4 → Políticas
        14: 4,  # WP4.0 → Políticas
        10: 5,  # WP5 → Data
        15: 5,  # WP5.0 → Data
        # 17, 18 → NULL (no sabemos qué son)
    }
    
    try:
        print("=" * 80)
        print("🔄 Remapping Invalid Work Packages")
        print("=" * 80)
        
        # Show mapping
        print("\n📋 Mapeo que se aplicará:")
        for old_wp, new_wp in wp_mapping.items():
            print(f"   WP {old_wp} → WP {new_wp}")
        
        print(f"\n   WP 17, 18 → NULL (sin mapeo claro)")
        
        # Apply remapping for academic_members (principal WP)
        total_updated = 0
        for old_wp, new_wp in wp_mapping.items():
            sql = text(f"UPDATE academic_members SET wp_id = {new_wp} WHERE wp_id = {old_wp};")
            result = db.execute(sql)
            total_updated += result.rowcount
        
        # Apply remapping for member_wps (many-to-many table)
        print("\n🔗 Remapeando tabla de relación muchos-a-muchos (member_wps)...")
        for old_wp, new_wp in wp_mapping.items():
            # Primero: Borrar si el nuevo ya existe (para evitar errores de clave única)
            sql_del = text(f"""
                DELETE FROM member_wps m1
                WHERE wp_id = {old_wp}
                AND EXISTS (
                    SELECT 1 FROM member_wps m2 
                    WHERE m2.member_id = m1.member_id 
                    AND m2.wp_id = {new_wp}
                );
            """)
            db.execute(sql_del)
            
            # Segundo: Actualizar los que quedan
            sql_upd = text(f"UPDATE member_wps SET wp_id = {new_wp} WHERE wp_id = {old_wp};")
            db.execute(sql_upd)
        
        # Set WP 17, 18 to NULL in academic_members
        res_null = db.execute(text("UPDATE academic_members SET wp_id = NULL WHERE wp_id IN (17, 18);"))
        null_count = res_null.rowcount
        
        # Final cleanup for member_wps (remove any reference to 6-18 that didn't map)
        db.execute(text("DELETE FROM member_wps WHERE wp_id > 5;"))
        
        db.commit()

        
        print(f"\n📊 Total investigadores actualizados: {total_updated}")
        if null_count > 0:
            print(f"⚠️  Investigadores puestos a NULL (WP 17/18): {null_count}")
        
        # Now delete invalid WPs from work_packages table
        print(f"\n🗑️  Borrando WPs inválidos (6-18) de la tabla work_packages...")
        sql = text("""
            DELETE FROM work_packages
            WHERE id > 5;
        """)
        result = db.execute(sql)
        deleted_count = result.rowcount
        db.commit()
        
        print(f"   ✅ Borrados {deleted_count} WPs inválidos")
        
        # Verify
        print(f"\n🔍 Verificación final:")
        sql = text("""
            SELECT wp_id, COUNT(*) as count
            FROM academic_members
            WHERE member_type = 'researcher' AND is_active = TRUE
            GROUP BY wp_id
            ORDER BY wp_id;
        """)
        distribution = db.execute(sql).fetchall()
        
        print(f"\n   Distribución de investigadores por WP:")
        for row in distribution:
            wp_name = f"WP {row.wp_id}" if row.wp_id else "Sin WP"
            print(f"   {wp_name}: {row.count} investigadores")
        
        print("\n" + "=" * 80)
        print("✅ Remapeo completado exitosamente!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    remap_wps()
