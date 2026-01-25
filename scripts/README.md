# 📚 Scripts de CECAN Backend

Organización de scripts por categoría funcional.

---

## 🌱 Seeds - Datos de Demostración (5 scripts)

Scripts para poblar la base de datos con datos de prueba.

```bash
# Crear usuarios demo (admin, pi, researcher, staff, student, viewer)
.venv/bin/python scripts/seeds/seed_users_demo.py

# Crear proyectos de demostración
.venv/bin/python scripts/seeds/seed_dummy_projects.py

# Crear RACI assignments de demostración
.venv/bin/python scripts/seeds/seed_responsibilities_demo.py

# Generar RACI desde Gantt
.venv/bin/python scripts/seeds/seed_responsibilities_from_gantt.py

# Seeds interactivos con escenarios realistas
.venv/bin/python scripts/seeds/seed_responsibilities_interactive.py
```

**Cuándo usar**: Al iniciar un nuevo entorno o después de resetear la BD.

---

## 🔄 Sync - Sincronización e Importación (13 scripts)

Scripts para sincronizar datos externos e importar archivos.

### Pipeline Completo
```bash
# Ejecutar pipeline de enriquecimiento completo
.venv/bin/python scripts/sync/run_enrichment.py

# Vincular investigadores con publicaciones (matching)
.venv/bin/python scripts/sync/run_matching.py
```

### Importación
```bash
# Importar personal desde Excel CECAN
.venv/bin/python scripts/sync/import_cecan_personnel.py

# Importar estudiantes desde Excel
.venv/bin/python scripts/sync/import_students_excel.py

# Importar PDFs locales a la base de datos
.venv/bin/python scripts/sync/import_local_pdfs.py

# Parser Excel → Gantt
.venv/bin/python scripts/sync/excel_to_gantt_parser.py
```

### Sincronización WOS
```bash
# Continuar scraping de WOS
.venv/bin/python scripts/sync/continue_wos_scraping.py

# Sincronizar WOS Excel → Base de datos
.venv/bin/python scripts/sync/sync_wos_excel_to_db.py

# Reconstruir Excel WOS desde BD
.venv/bin/python scripts/sync/reconstruct_wos_excel.py
```

**Cuándo usar**: Al actualizar datos desde fuentes externas.

---

## 🎨 Enrich - Enriquecimiento de Datos (9 scripts)

Scripts para enriquecer publicaciones con metadata adicional.

```bash
# Enriquecimiento batch con Scholar API
.venv/bin/python scripts/enrich/batch_enrich_all.py

# Enriquecimiento ORCID batch
.venv/bin/python scripts/enrich/enrich_orcids_batch.py

# Enriquecimiento desde web
.venv/bin/python scripts/enrich/enrich_from_web.py

# Extraer ORCIDs de PDFs
.venv/bin/python scripts/enrich/extract_orcids_from_pdfs.py

# Inferir autores desde DOI
.venv/bin/python scripts/enrich/infer_authors_from_doi.py

# Backfill de cuartiles
.venv/bin/python scripts/enrich/backfill_quartiles.py
```

**Cuándo usar**: Después de importar nuevas publicaciones.

---

## 🛠️ Tools - Herramientas (5 scripts)

Utilidades para administración y desarrollo.

```bash
# Obtener token JWT de autenticación
.venv/bin/python scripts/tools/get_auth_token.py admin@cecan.cl admin123

# Verificar estado de embeddings
.venv/bin/python scripts/tools/check_embeddings_status.py

# Gestionar usuarios vía CLI
.venv/bin/python scripts/tools/manage_users.py

# Gestionar datos de publicaciones
.venv/bin/python scripts/tools/manage_publications_data.py

# CLI de base de datos
.venv/bin/python scripts/tools/db_cli.py
```

**Cuándo usar**: Para tareas administrativas diarias.

---

## 🔍 Audit - Auditoría (11 scripts)

Scripts de verificación de integridad de datos.

```bash
# Auditoría de compliance
.venv/bin/python scripts/audit/audit_compliance.py

# Auditoría de consistencia ORCID
.venv/bin/python scripts/audit/audit_orcid_consistency.py

# Auditoría de personal
.venv/bin/python scripts/audit/audit_personnel.py

# Diagnóstico final completo
.venv/bin/python scripts/audit/final_diagnostic.py
```

**Cuándo usar**: Periódicamente para verificar calidad de datos.

---

## ✅ Verify - Verificación (6 scripts)

Scripts de testing y validación.

```bash
# Verificar integración Gantt ↔ My Tasks
.venv/bin/python scripts/verify/verify_gantt_integration.py

# Validar parsers
.venv/bin/python scripts/verify/validate_parser.py

# Test de inferencia de autores
.venv/bin/python scripts/verify/test_author_inference.py

# Reportes de matching
.venv/bin/python scripts/verify/matching_reports.py
```

**Cuándo usar**: Después de cambios importantes en el código.

---

## 🧹 Cleanup - Limpieza (13 scripts)

Scripts de mantenimiento y limpieza de base de datos.

```bash
# Limpiar base de datos
.venv/bin/python scripts/cleanup/clean_database.py

# Limpiar duplicados
.venv/bin/python scripts/cleanup/clean_duplicates_simple.py

# Limpiar asignaciones huérfanas
.venv/bin/python scripts/cleanup/cleanup_orphan_assignments.py

# Fix de problemas comunes
.venv/bin/python scripts/cleanup/fix_*.py
```

**Cuándo usar**: Al detectar inconsistencias o duplicados.

---

## 🐛 Debug - Debug y Diagnóstico (25 scripts)

Scripts de debugging para desarrollo. **Revisar si siguen en uso**.

```bash
# Debug de PDFs
.venv/bin/python scripts/debug/debug_pdfs.py

# Debug de Scholar
.venv/bin/python scripts/debug/debug_scholar_data.py

# Diagnósticos varios
.venv/bin/python scripts/debug/diagnose_*.py

# Checks específicos
.venv/bin/python scripts/debug/check_*.py
```

**Cuándo usar**: Solo durante desarrollo/debugging activo.

---

## 📦 Legacy - Archivado (19 scripts)

Scripts legacy archivados en `scripts/legacy/`. **No usar en producción**.

Mantenidos solo por historial. Si necesitas algo de aquí, revisa primero si hay una versión moderna.

---

## 🎯 Flujos Comunes

### Setup inicial
```bash
# 1. Seeds de usuarios demo
.venv/bin/python scripts/seeds/seed_users_demo.py

# 2. Importar datos
.venv/bin/python scripts/sync/import_cecan_personnel.py
.venv/bin/python scripts/sync/import_students_excel.py

# 3. Enriquecer
.venv/bin/python scripts/sync/run_enrichment.py
```

### Mantenimiento semanal
```bash
# 1. Auditoría
.venv/bin/python scripts/audit/audit_compliance.py

# 2. Matching
.venv/bin/python scripts/sync/run_matching.py

# 3. Limpieza
.venv/bin/python scripts/cleanup/cleanup_orphan_assignments.py
```

### Importación de nuevas publicaciones
```bash
# 1. Importar PDFs
.venv/bin/python scripts/sync/import_local_pdfs.py

# 2. Enriquecer
.venv/bin/python scripts/enrich/batch_enrich_all.py

# 3. Matching
.venv/bin/python scripts/sync/run_matching.py
```

---

## 📂 Estructura de Carpetas

```
scripts/
├── seeds/           (5)   - Datos demo
├── sync/            (13)  - Importación/sincronización
├── enrich/          (9)   - Enriquecimiento
├── tools/           (5)   - Utilidades admin
├── audit/           (11)  - Auditoría
├── verify/          (6)   - Verificación/testing
├── cleanup/         (13)  - Limpieza/mantenimiento
├── debug/           (25)  - Debug (revisar uso)
└── legacy/          (19)  - Archivado (no usar)
```

---

## ⚠️ Notas Importantes

1. **Siempre usar virtual environment**: `.venv/bin/python`
2. **Backup antes de cleanup**: Los scripts de limpieza modifican la BD
3. **Debug scripts**: Revisar si siguen siendo necesarios antes de usar
4. **Legacy**: No usar, mantenido solo por historial

---

## 🆘 Ayuda

Si un script falla:
1. Verificar que estás en el virtual environment
2. Revisar logs en consola
3. Verificar permisos de archivos
4. Consultar el código del script para ver qué hace

Para más información, revisar:
- `INFORME_ARCHIVOS.md` - Análisis completo
- `PLAN_LIMPIEZA.md` - Plan de reorganización
