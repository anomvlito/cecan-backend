#!/usr/bin/env python3
"""
Arregla los nombres problemáticos específicos separándolos en registros individuales
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def fix_names():
    print("=" * 80)
    print("🔧 CORRIGIENDO NOMBRES PROBLEMÁTICOS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Casos a corregir
    fixes = {
        "Alicia Colombo, Juan Carlos Roa": ["Alicia Colombo", "Juan Carlos Roa"],
        "Hector Contreras, Viviana Montecinos": ["Hector Contreras", "Viviana Montecinos"]
    }
    
    for bad_name, new_names in fixes.items():
        # Buscar el registro problemático (incluso si ya fue marcado con [REVISAR])
        cursor.execute("SELECT id FROM academic_members WHERE full_name LIKE ?", (f"%{bad_name}%",))
        result = cursor.fetchone()
        
        if not result:
            print(f"⚠️  No se encontró: {bad_name}")
            continue
            
        old_id = result[0]
        print(f"\nProcesando ID {old_id}: {bad_name}")
        
        # 1. Actualizar el registro existente con el primer nombre
        first_name = new_names[0]
        print(f"   ✏️  Actualizando ID {old_id} a '{first_name}'")
        cursor.execute("UPDATE academic_members SET full_name = ? WHERE id = ?", (first_name, old_id))
        
        # 2. Crear o verificar el segundo nombre
        second_name = new_names[1]
        cursor.execute("SELECT id FROM academic_members WHERE full_name = ?", (second_name,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"   ✅ '{second_name}' ya existe con ID {existing[0]}")
        else:
            print(f"   ➕ Creando nuevo registro para '{second_name}'")
            # Insertar nuevo investigador
            cursor.execute("INSERT INTO academic_members (full_name) VALUES (?)", (second_name,))
            new_id = cursor.lastrowid
            # Crear detalles vacíos para el nuevo investigador
            cursor.execute("INSERT INTO researcher_details (member_id) VALUES (?)", (new_id,))
            print(f"      Creado con ID {new_id}")

    conn.commit()
    conn.close()
    print("\n✅ Corrección completada")

if __name__ == "__main__":
    fix_names()
