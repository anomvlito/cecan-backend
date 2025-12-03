#!/usr/bin/env python3
"""
Script para reiniciar el servidor y sincronizar publicaciones
"""
import subprocess
import time
import sys

print("=" * 80)
print("🔄 REINICIO Y SINCRONIZACIÓN")
print("=" * 80)

print("\n📝 INSTRUCCIONES:")
print("-" * 80)
print("""
El error se ha corregido. Ahora necesitas:

1. **Detener el servidor actual**
   - Ve a la terminal donde está corriendo (la que muestra los errores)
   - Presiona CTRL+C para detenerlo

2. **Reiniciar el servidor**
   - En la misma terminal, ejecuta:
     python3 main.py

3. **Ejecutar la sincronización** (en otra terminal)
   - python3 scripts/sync_publications.py

El problema era que el scraper no estaba incluyendo los campos obligatorios
de compliance (has_valid_affiliation, has_funding_ack, anid_report_status).

Ahora estos campos se incluyen con valores por defecto:
- has_valid_affiliation: False
- has_funding_ack: False  
- anid_report_status: 'Error'

Estos valores se actualizarán después cuando ejecutes la auditoría de compliance.
""")

print("=" * 80)
print("✅ LISTO PARA REINICIAR")
print("=" * 80)
