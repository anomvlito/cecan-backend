# 🧹 PLAN DE LIMPIEZA - CECAN Backend

**Objetivo**: Organizar archivos sin romper la aplicación

---

## 🎯 FASE 1: IDENTIFICAR DUPLICADOS (CRÍTICO)

### Acción 1.1: Comparar rutas duplicadas

```bash
# Comparar projects.py vs scientific_projects.py
diff api/routes/projects.py api/routes/scientific_projects.py

# Comparar scholar_endpoints.py vs modules/scholar/routes.py
diff api/routes/scholar_endpoints.py modules/scholar/routes.py
```

**Decisión**:
- Si son idénticos → Eliminar el NO registrado en main.py
- Si son diferentes → Consolidar o renombrar

---

## 📦 FASE 2: REORGANIZAR ARCHIVOS (SIN ELIMINAR)

### Acción 2.1: Crear estructura de carpetas

```bash
cd cecan-backend

# Crear carpetas de organización
mkdir -p scripts/seeds
mkdir -p scripts/sync
mkdir -p scripts/enrich
mkdir -p scripts/tools
mkdir -p scripts/debug
mkdir -p scripts/audit
mkdir -p scripts/verify
mkdir -p scripts/cleanup
mkdir -p archive/legacy
mkdir -p archive/migrations_old
```

### Acción 2.2: Mover scripts por categoría

```bash
# SEEDS
mv scripts/seed_*.py scripts/seeds/

# SYNC
mv scripts/run_enrichment.py scripts/sync/
mv scripts/run_matching.py scripts/sync/
mv scripts/import_*.py scripts/sync/
mv scripts/sync_*.py scripts/sync/
mv scripts/excel_to_gantt_parser.py scripts/sync/

# ENRICH
mv scripts/enrich_*.py scripts/enrich/
mv scripts/extract_*.py scripts/enrich/
mv scripts/infer_*.py scripts/enrich/

# TOOLS
mv scripts/get_auth_token.py scripts/tools/
mv scripts/manage_*.py scripts/tools/
mv scripts/db_cli.py scripts/tools/

# AUDIT
mv scripts/audit_*.py scripts/audit/

# VERIFY
mv scripts/verify_*.py scripts/verify/
mv scripts/validate_*.py scripts/verify/
mv scripts/test_*.py scripts/verify/

# CLEANUP
mv scripts/clean_*.py scripts/cleanup/
mv scripts/cleanup_*.py scripts/cleanup/
mv scripts/fix_*.py scripts/cleanup/

# DEBUG (mover desde raíz también)
mv debug_*.py scripts/debug/
mv diagnose_*.py scripts/debug/
mv test_*.py scripts/debug/
mv create_scholar_table_direct.py scripts/debug/
mv fix_scholar_migration.py scripts/debug/
mv force_reenrich_test.py scripts/debug/
mv merge_scholar_endpoints.py scripts/debug/
mv verify_fix_simple.py scripts/debug/
```

### Acción 2.3: Archivar legacy

```bash
# Mover legacy de scripts/
mv scripts/legacy/* archive/legacy/

# Mover migraciones manuales
mv migrations/* archive/migrations_old/
# IMPORTANTE: NO tocar alembic/versions/
```

---

## 📝 FASE 3: CREAR DOCUMENTACIÓN

### Acción 3.1: README de scripts

```bash
cat > scripts/README.md << 'EOF'
# Scripts de CECAN Backend

## 🌱 Seeds (Datos de Demostración)
- `seeds/seed_users_demo.py` - Crear usuarios demo
- `seeds/seed_dummy_projects.py` - Proyectos de prueba
- `seeds/seed_responsibilities_*.py` - RACI assignments

## 🔄 Sync (Sincronización/Importación)
- `sync/run_enrichment.py` - Pipeline completo enriquecimiento
- `sync/run_matching.py` - Vincular investigadores-publicaciones
- `sync/import_cecan_personnel.py` - Importar personal Excel
- `sync/import_students_excel.py` - Importar estudiantes
- `sync/import_local_pdfs.py` - PDFs locales → BD

## 🎨 Enrich (Enriquecimiento de Datos)
- `enrich/enrich_orcids_batch.py` - ORCID batch
- `enrich/extract_orcids_batch.py` - Extraer ORCIDs
- `enrich/infer_authors_from_doi.py` - Inferir autores

## 🛠️ Tools (Herramientas)
- `tools/get_auth_token.py` - Obtener JWT token
- `tools/manage_users.py` - Gestión usuarios CLI
- `tools/db_cli.py` - CLI base de datos

## 🔍 Audit (Auditoría)
Scripts de verificación de integridad de datos.

## ✅ Verify (Verificación)
Scripts de testing y validación.

## 🧹 Cleanup (Limpieza)
Scripts de mantenimiento y limpieza de BD.

## 🐛 Debug (Debug y Diagnóstico)
Scripts de debugging - revisar si siguen en uso.

---

## Uso

### Crear usuarios demo
```bash
.venv/bin/python scripts/seeds/seed_users_demo.py
```

### Ejecutar enriquecimiento
```bash
.venv/bin/python scripts/sync/run_enrichment.py
```

### Obtener token de autenticación
```bash
.venv/bin/python scripts/tools/get_auth_token.py admin@cecan.cl admin123
```
EOF
```

### Acción 3.2: Actualizar .gitignore

```bash
cat >> .gitignore << 'EOF'

# Archive (legacy files)
archive/

# Debug scripts (si no se usan en producción)
scripts/debug/

# WOS Excel (muy grande)
*.xlsx
wos_*.xlsx
EOF
```

---

## 🗑️ FASE 4: EVALUAR ELIMINACIÓN (OPCIONAL)

### Candidatos para eliminación (verificar primero)

```bash
# 1. Rutas duplicadas (después de comparar en Fase 1)
# rm api/routes/projects.py  # SI es duplicado
# rm api/routes/scholar_endpoints.py  # SI es duplicado

# 2. Archivos muy pequeños/experimentales
# rm scripts/debug/merge_scholar_endpoints.py  # 391 bytes

# 3. Legacy ya archivado (después de mover a archive/)
# rm -rf archive/legacy/
# rm -rf archive/migrations_old/

# 4. Backups SQL vacíos
# find archive/migrations_old -name "backup_*.sql" -size 0 -delete
```

**⚠️ IMPORTANTE**:
- NO eliminar nada sin verificar primero
- Hacer backup git antes: `git commit -am "backup before cleanup"`
- Probar que la app funcione después de cada paso

---

## ✅ FASE 5: VERIFICACIÓN POST-LIMPIEZA

### Checklist

```bash
# 1. Verificar que el servidor inicia
make kill
make backend
curl http://localhost:8000/health

# 2. Verificar imports críticos
.venv/bin/python -c "
from main import app
from core.models import User, Publication, ScientificProject
from services.rag_service import get_semantic_engine
print('✅ Imports OK')
"

# 3. Verificar que los scripts seed funcionan
.venv/bin/python scripts/seeds/seed_users_demo.py

# 4. Verificar rutas registradas
grep "include_router" main.py | wc -l
# Debería ser 22

# 5. Verificar base de datos
.venv/bin/alembic current
# Debería mostrar: cc2078af8b8c (head)
```

---

## 📊 RESULTADO ESPERADO

### Antes
```
cecan-backend/
├── debug_*.py (8 archivos en raíz)
├── scripts/ (97 archivos mezclados)
└── migrations/ (15 legacy)
```

### Después
```
cecan-backend/
├── main.py, config.py, schemas.py  ← Limpio
├── scripts/
│   ├── seeds/           (5)
│   ├── sync/            (7)
│   ├── enrich/          (8)
│   ├── tools/           (4)
│   ├── audit/           (14)
│   ├── verify/          (10)
│   ├── cleanup/         (10)
│   ├── debug/           (39)  ← Consolidado
│   └── README.md        ← Documentado
│
└── archive/
    ├── legacy/          (19)  ← Archivado
    └── migrations_old/  (15)  ← Archivado
```

---

## 🎯 BENEFICIOS

1. **Organización clara**: Scripts por categoría
2. **Raíz limpia**: Solo archivos core
3. **Documentación**: README explica uso
4. **Legacy separado**: No se pierde historial
5. **Fácil navegación**: Estructura lógica

---

## ⏱️ TIEMPO ESTIMADO

- **Fase 1**: 15 minutos (comparar duplicados)
- **Fase 2**: 30 minutos (reorganizar archivos)
- **Fase 3**: 15 minutos (documentación)
- **Fase 4**: Opcional (evaluar caso por caso)
- **Fase 5**: 10 minutos (verificación)

**TOTAL**: ~1-1.5 horas

---

## 🚨 IMPORTANTE

**Antes de empezar**:
```bash
git status
git add .
git commit -m "backup antes de limpieza de archivos"
```

**Ejecutar por fases**: No hacer todo de golpe, ir fase por fase y verificar.

**Mantener backup**: No eliminar nada hasta confirmar que todo funciona.
