#!/usr/bin/env python3
"""
Genera variaciones de nombres para mejorar matching
Agrega campos first_name, last_name, name_variations a researcher_details
"""
import sqlite3
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def generate_name_variations(full_name):
    """
    Genera variaciones comunes de un nombre
    Ejemplo: "Rodolfo Mancilla" -> ["R. Mancilla", "Mancilla R.", "R Mancilla", etc.]
    """
    parts = full_name.strip().split()
    
    if len(parts) < 2:
        return []
    
    # Asumimos: primeras palabras = nombres, última = apellido
    first_names = parts[:-1]
    last_name = parts[-1]
    
    variations = []
    
    # Variación 1: Inicial + Apellido (R. Mancilla)
    first_initial = first_names[0][0]
    variations.append(f"{first_initial}. {last_name}")
    variations.append(f"{first_initial} {last_name}")
    
    # Variación 2: Apellido + Inicial (Mancilla R.)
    variations.append(f"{last_name} {first_initial}.")
    variations.append(f"{last_name} {first_initial}")
    
    # Variación 3: Apellido, Nombre (Mancilla, Rodolfo)
    variations.append(f"{last_name}, {' '.join(first_names)}")
    
    # Variación 4: Solo apellido (para casos muy generales)
    variations.append(last_name)
    
    # Variación 5: Nombre completo sin espacios extras
    variations.append(full_name)
    
    return list(set(variations))  # Eliminar duplicados

def add_name_fields():
    """
    Agrega campos de nombre a researcher_details si no existen
    """
    print("=" * 80)
    print("📝 AGREGANDO CAMPOS DE NOMBRE")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar si las columnas ya existen
    cursor.execute("PRAGMA table_info(researcher_details)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Agregar columnas si no existen
    if 'first_name' not in columns:
        print("\n➕ Agregando columna 'first_name'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN first_name TEXT")
    
    if 'last_name' not in columns:
        print("➕ Agregando columna 'last_name'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN last_name TEXT")
    
    if 'name_variations' not in columns:
        print("➕ Agregando columna 'name_variations'...")
        cursor.execute("ALTER TABLE researcher_details ADD COLUMN name_variations TEXT")
    
    conn.commit()
    
    # Poblar campos
    print("\n🔄 Generando variaciones de nombres...")
    print("-" * 80)
    
    cursor.execute("""
        SELECT am.id, am.full_name
        FROM academic_members am
        JOIN researcher_details rd ON am.id = rd.member_id
    """)
    
    researchers = cursor.fetchall()
    updated = 0
    
    for member_id, full_name in researchers:
        # Saltar nombres con comas (son errores)
        if ',' in full_name and full_name.count(',') > 1:
            continue
        
        parts = full_name.strip().split()
        
        if len(parts) >= 2:
            first_names = ' '.join(parts[:-1])
            last_name = parts[-1]
            
            # Generar variaciones
            variations = generate_name_variations(full_name)
            variations_str = '|'.join(variations)  # Separar con |
            
            # Actualizar
            cursor.execute("""
                UPDATE researcher_details
                SET first_name = ?,
                    last_name = ?,
                    name_variations = ?
                WHERE member_id = ?
            """, (first_names, last_name, variations_str, member_id))
            
            updated += 1
            
            if updated <= 5:
                print(f"✅ {full_name}")
                print(f"   → Variaciones: {variations_str[:80]}...")
    
    conn.commit()
    conn.close()
    
    print(f"\n" + "=" * 80)
    print(f"📊 RESUMEN")
    print("=" * 80)
    print(f"✅ Investigadores actualizados: {updated}")
    print("\n💡 Ahora puedes usar estas variaciones para matching mejorado")
    print("   Re-ejecuta: python3 scripts/run_matching_improved.py")

if __name__ == "__main__":
    add_name_fields()
