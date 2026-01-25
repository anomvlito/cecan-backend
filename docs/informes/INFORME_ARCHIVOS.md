# 📊 INFORME DE ARCHIVOS - CECAN Backend

**Fecha**: 2026-01-25
**Total archivos Python**: 238+

---

## 🎯 RESUMEN EJECUTIVO

| Categoría | Cantidad | Estado |
|-----------|----------|--------|
| **CORE (Críticos)** | 77 archivos | ✅ Necesarios |
| **Utilidades Activas** | 32 scripts | ✅ Útiles |
| **Debug/Desarrollo** | 65+ scripts | ⚠️ Revisar uso |
| **Posiblemente Obsoletos** | 40+ archivos | ⚠️ Evaluar eliminación |

---

## 1. ✅ CORE (CRÍTICOS - NO TOCAR)

### Archivos Raíz (3)
```
main.py              - Punto de entrada FastAPI
config.py            - Configuración centralizada
schemas.py           - Validación Pydantic (20K, 689 líneas)
```

### /core (4 archivos)
```
models.py            - SQLAlchemy ORM (34K, 1082 líneas)
security.py          - JWT authentication
model_utils.py       - Utilidades para modelos
__init__.py
```

### /database (6 archivos)
```
session.py           - Gestión de sesiones SQLAlchemy
init.py              - Inicialización
seed.py              - Datos iniciales
legacy_wrapper.py    - Compatibilidad legacy
repositories/        - Repositorios
```

### /api/routes (22 REGISTRADAS EN main.py) ✅
```
✅ auth.py                    - Login, JWT
✅ users.py                   - Gestión usuarios
✅ responsibilities.py        - RACI, /my-dashboard
✅ compliance.py              - Compliance
✅ publications.py            - CRUD publicaciones
✅ enrichment.py              - Pipeline enriquecimiento
✅ researchers.py             - Investigadores
✅ rag.py                     - Chat RAG/FAISS
✅ dashboard.py               - Dashboard
✅ members.py                 - Miembros académicos
✅ files.py                   - Archivos
✅ reports.py                 - Reportes
✅ public.py                  - Endpoints públicos
✅ catalogs.py                - Journals, WPs
✅ external/ (3 archivos)     - OpenAlex, DOI, análisis
✅ students.py                - Estudiantes
✅ system/explorer.py         - Explorador sistema
✅ analytics.py               - Analítica
✅ scientific_projects.py     - Proyectos científicos
✅ research_map.py            - Mapa investigación
✅ exports.py                 - Exportación
✅ scholar_router             - Scholar Intelligence (en modules/)
```

### /services (23 ACTIVOS) ✅
```
auth_service.py              - Autenticación
authz.py                     - Autorización RACI
publication_service.py       - CRUD publicaciones
enrichment_service.py        - Pipeline enriquecimiento
openalex_service.py          - OpenAlex API
journal_service.py           - Journals
rag_service.py               - RAG/Vector store
student_service.py           - Estudiantes
analytics_service.py         - Analítica
research_map_service.py      - Mapa investigación
scholar_enrichment.py        - Scholar API
matching_service.py          - Matching autor-pub
agent_service.py             - Agentes IA
+ 10 servicios más...
```

### /alembic/versions (18 MIGRACIONES APLICADAS) ✅
```
309c9004d180  - Initial schema
f72778819959  - Scientific projects
14985a79356b  - RACI assignments
cc2078af8b8c  - Remove gantt tables ← NUEVA
+ 14 más...
```

---

## 2. ✅ UTILIDADES ACTIVAS (Usar regularmente)

### Seeds/Demo Data (5)
```
scripts/seed_users_demo.py                      - Usuarios demo (admin, pi, etc.)
scripts/seed_dummy_projects.py                  - Proyectos prueba
scripts/seed_responsibilities_demo.py           - RACI assignments demo
scripts/seed_responsibilities_from_gantt.py     - RACI desde Gantt
scripts/seed_responsibilities_interactive.py    - Seeds interactivos
```

### Sincronización/Importación (7)
```
scripts/run_enrichment.py                - Pipeline completo
scripts/run_matching.py                  - Vincular investigadores-pubs
scripts/import_cecan_personnel.py        - Importar personal Excel
scripts/import_students_excel.py         - Importar estudiantes
scripts/import_local_pdfs.py             - Importar PDFs locales
scripts/excel_to_gantt_parser.py         - Parser Excel → Gantt
scripts/sync_publications.py             - Sincronizar publicaciones
```

### Enriquecimiento (8)
```
batch_enrich_all.py                      - Batch Scholar (RAÍZ)
check_embeddings_status.py               - Estado embeddings (RAÍZ)
scripts/enrich_orcids_batch.py           - ORCID batch
scripts/enrich_from_web.py               - Web scraping
scripts/extract_orcids_batch.py          - Extraer ORCIDs
scripts/infer_authors_from_doi.py        - Inferir autores DOI
scripts/enrich_deep_scraping.py          - Scraping profundo
```

### WOS Integration (3)
```
continue_wos_scraping.py                 - Continuar WOS (RAÍZ)
sync_wos_excel_to_db.py                  - WOS Excel → DB (RAÍZ)
reconstruct_wos_excel.py                 - Reconstruir Excel (RAÍZ)
```

---

## 3. ⚠️ DEBUG/DESARROLLO (Revisar si sigues usando)

### Debug en Raíz (8 archivos)
```
❓ debug_pdfs.py                        - Debug extracción PDF
❓ debug_research_map.py                - Debug mapa investigación
❓ debug_scholar_data.py                - Debug Scholar
❓ diagnose_scholar_embeddings.py       - Diagnóstico embeddings
❓ fix_scholar_migration.py             - Fix migración
❓ force_reenrich_test.py               - Test re-enriquecimiento
❓ test_scholar_api.py                  - Test API Scholar
❓ create_scholar_table_direct.py       - Crear tabla directo
```

### Verificación (10)
```
scripts/verify_gantt_integration.py
scripts/validate_parser.py
scripts/test_author_inference.py
scripts/test_researcher_query.py
scripts/matching_reports.py
+ 5 más...
```

### Auditoría (14)
```
scripts/audit_compliance.py
scripts/audit_data_reconciliation.py
scripts/audit_language.py
scripts/audit_orcid_consistency.py
scripts/audit_orcids.py
scripts/audit_personnel.py
+ 8 más...
```

### Limpieza/Mantenimiento (10)
```
scripts/clean_database.py
scripts/clean_duplicates_simple.py
scripts/cleanup_orphan_assignments.py
+ 7 más...
```

### Diagnostic (20+)
```
scripts/check_*.py (5 scripts)
scripts/diag_*.py (4 scripts)
scripts/inspect_*.py (7 scripts)
+ más...
```

### Herramientas (4)
```
✅ scripts/get_auth_token.py            - Token autenticación
✅ scripts/manage_users.py              - Gestionar usuarios
✅ scripts/manage_publications_data.py  - Gestionar pubs
✅ scripts/db_cli.py                    - CLI base datos
```

---

## 4. 🗑️ POSIBLEMENTE OBSOLETOS

### Rutas NO Registradas (2)
```
❌ api/routes/projects.py              - ¿Duplicado de scientific_projects.py?
❌ api/routes/scholar_endpoints.py     - ¿Duplicado de modules/scholar/routes.py?
```

### Comentadas en main.py (1)
```
# api/routes/gantt.py                  - REMOVED: usando project_activities
```

### Legacy (19 scripts en scripts/legacy/)
```
scripts/legacy/debug_*.py (8 archivos)
scripts/legacy/audit_db_structure.py
scripts/legacy/migrate_*.py (3 archivos)
scripts/legacy/scrape_wos_*.py (2 archivos)
+ 5 más...
```

### Experimental/Duplicados (8)
```
❓ merge_scholar_endpoints.py (391 bytes) - Muy pequeño
❓ scripts/run_matching_improved.py        - Versión "_improved"
❓ scripts/scrape_wos_sample_v3.py         - Versión "v3"
+ experimental_service.py en services/
```

### Migración Manual Legacy (15 en /migrations)
```
❌ migrations/seed_database.py          - Legacy (usar alembic seeds)
❌ migrations/migrate_to_english.py     - Ya completada
❌ migrations/*.sql                     - Scripts manuales (no alembic)
❌ migrations/backup_*.sql              - Backups viejos
```

### Tests (3)
```
tests/test_audit.py
tests/test_report.py
tests/verify_fields_script.py
```

---

## 5. 🔍 DISCREPANCIAS IMPORTANTES

### ⚠️ Rutas que existen pero NO están registradas:
1. **`api/routes/projects.py`**
   - Estado: Existe pero no en main.py
   - Posible duplicado de `scientific_projects.py` (que SÍ está)
   - **Acción**: Verificar contenido, posiblemente eliminar

2. **`api/routes/scholar_endpoints.py`**
   - Estado: Existe pero no en main.py
   - Posible duplicado de `modules/scholar/routes.py` (registrado)
   - **Acción**: Comparar y eliminar si redundante

3. **`api/routes/gantt.py`**
   - Estado: Comentado explícitamente en main.py
   - Razón: "Gantt tables deleted, using project_activities"
   - **Acción**: Dejar comentado (ya decidido)

---

## 6. 📦 MÓDULO ESPECIAL: Scholar Intelligence

**Ubicación**: `/modules/scholar/` (4 archivos)

```
✅ __init__.py     - Router export
✅ routes.py       - Endpoints Scholar
✅ client.py       - Cliente HTTP Scholar API
✅ models.py       - Modelos Scholar
```

**Estado**: ACTIVO (registrado en main.py)

---

## 7. 🔄 FLUJOS PRINCIPALES

### Flujo de Publicaciones
```
1. Upload PDF → publications.py
2. Text extraction → publication_service.py
3. DOI detection → enrichment.py (Phase 1)
4. OpenAlex lookup → openalex_service.py
5. Journal matching → journal_service.py
6. FAISS indexing → rag_service.py
7. Scholar enrichment → scholar_enrichment.py
8. AI summaries → Gemini (Phase 2)
```

### Flujo RACI
```
1. Create assignment → responsibilities.py POST
2. Link member → ResponsibilityAssignment
3. My Dashboard → responsibilities.py GET /my-dashboard
4. Gantt integration → seed_responsibilities_from_gantt.py
```

### Flujo Enriquecimiento
```
1. Batch trigger → batch_enrich_all.py
2. Scholar enrichment → scholar_enrichment.py
3. ORCID metadata → orcid_metadata_service.py
4. WOS verification → wos_verification_service.py
5. Índice actualizado → FAISS vectorstore
```

---

## 8. 📋 RECOMENDACIONES DE LIMPIEZA

### 🔴 CRÍTICO - Resolver inmediatamente
1. **Verificar duplicados de rutas**:
   - Comparar `projects.py` vs `scientific_projects.py`
   - Comparar `scholar_endpoints.py` vs `modules/scholar/routes.py`

### 🟡 IMPORTANTE - Hacer pronto
2. **Consolidar scripts legacy**:
   - Archivar `/scripts/legacy/` (19 archivos)
   - Considerar mover a carpeta `archive/` o eliminar

3. **Limpiar migraciones manuales**:
   - `/migrations/` tiene 15 archivos legacy
   - Ya tienes 18 migraciones en alembic/versions/
   - Archivar o eliminar migrations/ legacy

### 🟢 OPCIONAL - Cuando tengas tiempo
4. **Revisar scripts de debug en raíz** (8 archivos):
   - Si ya no debugueas, mover a `/scripts/debug/`
   - O eliminar si ya no se usan

5. **Documentar scripts activos**:
   - Crear `/scripts/README.md` explicando qué hace cada uno
   - Marcar cuáles son esenciales vs opcionales

6. **Tests**:
   - Solo tienes 3 archivos de tests
   - Considerar ampliar coverage

---

## 9. 🎯 ESTRUCTURA RECOMENDADA

```
cecan-backend/
├── main.py                    ✅ CORE
├── config.py                  ✅ CORE
├── schemas.py                 ✅ CORE
│
├── core/                      ✅ CORE (4 archivos)
├── database/                  ✅ CORE (6 archivos)
├── api/routes/                ✅ CORE (22 activos)
├── services/                  ✅ CORE (23 activos)
├── alembic/versions/          ✅ CORE (18 migraciones)
│
├── modules/scholar/           ✅ ACTIVO (4 archivos)
│
├── scripts/
│   ├── seeds/                 ✅ ÚTILES (5 scripts)
│   ├── sync/                  ✅ ÚTILES (7 scripts)
│   ├── enrich/                ✅ ÚTILES (8 scripts)
│   ├── tools/                 ✅ ÚTILES (4 scripts)
│   ├── audit/                 ⚠️ REVISAR (14 scripts)
│   ├── verify/                ⚠️ REVISAR (10 scripts)
│   ├── cleanup/               ⚠️ REVISAR (10 scripts)
│   ├── debug/                 ⚠️ REVISAR (8 en raíz + otros)
│   └── archive/               🗑️ MOVER LEGACY (19 + 15)
│
└── tests/                     ✅ ÚTILES (3 scripts)
```

---

## 10. 📊 ESTADÍSTICAS FINALES

### Por Categoría
- **CORE Necesario**: 77 archivos (32%)
- **Utilidades Activas**: 32 archivos (13%)
- **Debug/Desarrollo**: 65+ archivos (27%)
- **Posiblemente Obsoletos**: 40+ archivos (17%)
- **Otros**: ~24 archivos (10%)

### Por Estado
- ✅ **Mantener**: 109 archivos (45%)
- ⚠️ **Revisar uso**: 65 archivos (27%)
- 🗑️ **Evaluar eliminación**: 40+ archivos (17%)
- ❓ **Pendiente investigar**: 24 archivos (10%)

---

## ✅ CONCLUSIÓN

El proyecto está **bien estructurado** con separación clara entre:
- CORE (funcional y crítico)
- Utilidades (scripts útiles)
- Debug/Desarrollo (revisar si siguen en uso)

**Principales acciones**:
1. ✅ Resolver rutas duplicadas (projects.py, scholar_endpoints.py)
2. ✅ Archivar `/scripts/legacy/` y `/migrations/` legacy
3. ✅ Mover debug scripts de raíz a `/scripts/debug/`
4. ✅ Documentar scripts activos

**Estado general**: ⭐⭐⭐⭐ (4/5)
- Código CORE limpio
- Mucho "cruft" acumulado de desarrollo
- Necesita limpieza de archivos obsoletos
