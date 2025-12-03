#!/usr/bin/env python3
"""
Script para depurar qué se guardó en la BD
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("🔍 DEBUG: Verificando datos guardados")
print("=" * 80)

# Ver 3 publicaciones actualizadas
cursor.execute("""
    SELECT id, titulo, autores, fecha, url_origen 
    FROM publicaciones 
    WHERE id IN (2, 3, 4)
""")

print("\n📄 MUESTRA DE PUBLICACIONES:")
for row in cursor.fetchall():
    id_val, titulo, autores, fecha, url = row
    print(f"\n[{id_val}] {titulo[:60]}...")
    print(f"    autores type: {type(autores)}, value: '{autores}', len: {len(autores) if autores else 0}")
    print(f"    fecha type: {type(fecha)}, value: '{fecha}', len: {len(fecha) if fecha else 0}")
    print(f"    url type: {type(url)}, value: '{url[:50] if url else 'None'}...'")

# Contar diferentes estados
cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE autores IS NULL")
null_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE autores = ''")
empty_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE autores IS NOT NULL AND autores != ''")
filled_count = cursor.fetchone()[0]

print(f"\n📊 ESTADÍSTICAS DE AUTORES:")
print(f"   NULL:     {null_count}")
print(f"   Vacío:    {empty_count}")
print(f"   Lleno:    {filled_count}")

conn.close()
