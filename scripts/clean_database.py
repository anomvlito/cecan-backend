#!/usr/bin/env python3
"""
Limpia duplicados y corrige nombres problemáticos
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def clean_database():
    print("=" * 80)
    print("🧹 LIMPIEZA DE BASE DE DATOS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. ELIMINAR PUBLICACIONES DUPLICADAS
    print("\n📚 PASO 1: Eliminando publicaciones duplicadas...")
    print("-" * 80)
    
    # Encontrar duplicados
    cursor.execute("""
        SELECT titulo, MIN(id) as keep_id, GROUP_CONCAT(id) as all_ids, COUNT(*) as count
        FROM publicaciones
        GROUP BY titulo
        HAVING count > 1
    """)
    
    duplicates = cursor.fetchall()
    total_to_delete = 0
    
    for titulo, keep_id, all_ids, count in duplicates:
        ids = [int(x) for x in all_ids.split(',')]
        ids_to_delete = [x for x in ids if x != keep_id]
        
        if ids_to_delete:
            placeholders = ','.join('?' * len(ids_to_delete))
            
            # Eliminar relaciones primero
            cursor.execute(f"""
                DELETE FROM investigador_publicacion 
                WHERE publicacion_id IN ({placeholders})
            """, ids_to_delete)
            
            # Eliminar publicaciones
            cursor.execute(f"""
                DELETE FROM publicaciones 
                WHERE id IN ({placeholders})
            """, ids_to_delete)
            
            total_to_delete += len(ids_to_delete)
            
            if total_to_delete <= 10:
                print(f"   🗑️  Eliminando duplicados de: {titulo[:60]}...")
                print(f"      Manteniendo ID {keep_id}, eliminando {ids_to_delete}")
    
    print(f"\n   ✅ Eliminadas {total_to_delete} publicaciones duplicadas")
    
    # 2. CORREGIR NOMBRES CON COMAS
    print("\n\n👥 PASO 2: Corrigiendo nombres con comas...")
    print("-" * 80)
    
    # Caso 1: "Alicia Colombo, Juan Carlos Roa" -> Dividir en 2
    cursor.execute("""
        SELECT id, full_name
        FROM academic_members
        WHERE full_name LIKE '%,%'
    """)
    
    problematic = cursor.fetchall()
    
    for member_id, full_name in problematic:
        print(f"\n   ⚠️  Nombre problemático: [{member_id}] {full_name}")
        print(f"      Acción: Marcar para revisión manual")
        
        # Opción: Comentar el registro para revisión manual
        # No lo eliminamos porque podría tener datos importantes
        cursor.execute("""
            UPDATE academic_members
            SET full_name = ?
            WHERE id = ?
        """, (f"[REVISAR] {full_name}", member_id))
    
    print(f"\n   ✅ Marcados {len(problematic)} nombres para revisión manual")
    
    conn.commit()
    
    # 3. ESTADÍSTICAS FINALES
    print("\n\n" + "=" * 80)
    print("📊 ESTADÍSTICAS DESPUÉS DE LIMPIEZA")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM publicaciones")
    total_pubs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM academic_members")
    total_members = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM investigador_publicacion")
    total_matches = cursor.fetchone()[0]
    
    print(f"""
    📚 Publicaciones:           {total_pubs}
    👨‍🔬 Investigadores:          {total_members}
    🔗 Relaciones:              {total_matches}
    
    🗑️  Duplicados eliminados:  {total_to_delete}
    ⚠️  Nombres marcados:       {len(problematic)}
    """)
    
    conn.close()
    
    print("=" * 80)
    print("💡 PRÓXIMOS PASOS")
    print("=" * 80)
    print("""
    1. Revisa manualmente los nombres marcados con [REVISAR]
    2. Corrige en la fuente de datos original
    3. Re-ejecuta matching: python3 scripts/run_matching.py
    4. Agrega variaciones de nombres: python3 scripts/add_name_variations.py
    """)

if __name__ == "__main__":
    response = input("⚠️  Esto eliminará duplicados. ¿Continuar? (escribe 'SI'): ")
    if response == 'SI':
        clean_database()
    else:
        print("❌ Cancelado")
