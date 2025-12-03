#!/usr/bin/env python3
"""
Verificar esquema de tabla investigador_publicacion
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("🔍 Verificando esquema de investigador_publicacion...")
cursor.execute("PRAGMA table_info(investigador_publicacion)")
columns = cursor.fetchall()

if columns:
    print("\n✅ Columnas encontradas:")
    for col in columns:
        col_id, col_name, col_type, not_null, default, pk = col
        print(f"   - {col_name:20} {col_type:15} {'PK' if pk else ''}")
else:
    print("\n❌ Tabla no existe o está vacía")

conn.close()
