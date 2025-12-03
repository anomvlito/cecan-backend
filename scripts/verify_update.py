#!/usr/bin/env python3
"""
Script para ver qué datos se actualizaron realmente
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("🔍 VERIFICANDO DATOS ACTUALIZADOS")
print("=" * 80)

# Ver una muestra de publicaciones
cursor.execute("""
    SELECT id, titulo, autores, fecha, url_origen 
    FROM publicaciones 
    LIMIT 5
""")

print("\n📄 MUESTRA DE 5 PUBLICACIONES:")
print("-" * 80)

for row in cursor.fetchall():
    id_val, titulo, autores, fecha, url = row
    print(f"\n[{id_val}] {titulo[:60]}...")
    print(f"    Autores: {autores if autores else '❌ VACÍO'}")
    print(f"    Fecha:   {fecha if fecha else '❌ VACÍO'}")
    print(f"    URL:     {url[:60] if url else '❌ VACÍO'}...")

# Estadísticas
cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE autores IS NOT NULL AND autores != ''")
with_authors = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE fecha IS NOT NULL AND fecha != ''")
with_dates = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM publicaciones WHERE url_origen IS NOT NULL AND url_origen != ''")
with_urls = cursor.fetchone()[0]

total = 151

print("\n" + "=" * 80)
print("📊 ESTADÍSTICAS")
print("=" * 80)
print(f"Autores:  {with_authors}/{total} ({with_authors/total*100:.1f}%)")
print(f"Fechas:   {with_dates}/{total} ({with_dates/total*100:.1f}%)")
print(f"URLs:     {with_urls}/{total} ({with_urls/total*100:.1f}%)")

conn.close()
