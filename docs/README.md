# 📚 Documentación CECAN Backend

Índice maestro de documentación del proyecto.

---

## 🎯 Inicio Rápido

- **[README.md](../README.md)** - Documentación principal del proyecto
- **[CLAUDE.md](../CLAUDE.md)** - Guía para Claude Code (IA)
- **[scripts/README.md](../scripts/README.md)** - Guía de scripts organizados

---

## 📊 Informes y Análisis

### Análisis de Archivos (2026-01-25)
- **[INFORME_ARCHIVOS.md](informes/INFORME_ARCHIVOS.md)** - Análisis completo de 238+ archivos
- **[PLAN_LIMPIEZA.md](informes/PLAN_LIMPIEZA.md)** - Plan de reorganización ejecutado
- **[RESUMEN_LIMPIEZA.txt](informes/RESUMEN_LIMPIEZA.txt)** - Resumen visual rápido

**Estado**: ✅ Plan ejecutado exitosamente

---

## 🛠️ Utilidades

- **[GUIA_RAPIDA_DATOS.md](utilidades/GUIA_RAPIDA_DATOS.md)** - Guía rápida de datos

---

## 📂 Estructura del Proyecto

```
cecan-backend/
├── main.py                 - Punto de entrada FastAPI
├── config.py               - Configuración
├── schemas.py              - Validación Pydantic
│
├── core/                   - Modelos y seguridad
│   ├── models.py           - SQLAlchemy ORM
│   └── security.py         - JWT auth
│
├── api/routes/             - Endpoints REST
│   ├── auth.py
│   ├── publications.py
│   ├── scientific_projects.py
│   └── ... (22 rutas activas)
│
├── services/               - Lógica de negocio
│   ├── rag_service.py      - RAG/Vector store
│   ├── enrichment_service.py
│   └── ... (23 servicios)
│
├── database/               - Gestión BD
│   ├── session.py
│   └── repositories/
│
├── scripts/                - Utilidades organizadas
│   ├── seeds/              (5) - Datos demo
│   ├── sync/               (13) - Importación
│   ├── enrich/             (9) - Enriquecimiento
│   ├── tools/              (5) - Admin
│   ├── audit/              (11) - Auditoría
│   ├── verify/             (6) - Testing
│   ├── cleanup/            (13) - Limpieza
│   ├── debug/              (25) - Debug
│   └── README.md           - Guía de scripts
│
├── alembic/                - Migraciones BD
│   └── versions/           (18 migraciones)
│
├── docs/                   - Documentación
│   ├── informes/           - Análisis y reportes
│   ├── utilidades/         - Guías rápidas
│   └── README.md           - Este archivo
│
└── archive/                - Archivado (no usar)
    ├── legacy/             (19) - Scripts legacy
    ├── migrations_old/     (15) - Migraciones manuales
    ├── unused_routes/      (2) - Rutas no registradas
    └── data_backups/       - Backups de datos
```

---

## 🚀 Flujos Principales

### Setup Inicial
```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Aplicar migraciones
.venv/bin/alembic upgrade head

# 3. Crear usuarios demo
.venv/bin/python scripts/seeds/seed_users_demo.py

# 4. Iniciar servidor
make backend
```

### Desarrollo Diario
```bash
# Iniciar ambos (backend + frontend)
make dev

# Solo backend
make backend

# Solo frontend
make frontend

# Detener todo
make kill
```

### Mantenimiento
```bash
# Auditoría de datos
.venv/bin/python scripts/audit/audit_compliance.py

# Enriquecer publicaciones
.venv/bin/python scripts/enrich/batch_enrich_all.py

# Vincular autores
.venv/bin/python scripts/sync/run_matching.py
```

---

## 📖 Documentación Técnica

### API
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

### Base de Datos
- **Tipo**: PostgreSQL
- **URL**: `postgresql://cecan_user:cecan_password@localhost:5432/cecan_db`
- **Migraciones**: Alembic

### Autenticación
- **Método**: JWT (HS256)
- **Token expira**: 24 horas
- **Roles**: super_admin, admin, staff, pi, researcher, student, viewer

---

## 🎯 Sistema RAG (Chatbot)

### Estado Actual (2026-01-25)
✅ **Funcionando correctamente**

- Embeddings: FAISS + Gemini text-embedding-004
- Guardado en disco: `data/vectorstore/projects/`
- Datos indexados: 8 proyectos + 37 actividades
- Chunks de publicaciones: 7,628

### Uso
```bash
# Verificar estado
.venv/bin/python scripts/tools/check_embeddings_status.py

# Regenerar índice
curl -X POST http://localhost:8000/api/rag/refresh
```

---

## 🗄️ Archivado

Los siguientes archivos están archivados en `/archive` y **NO deben usarse**:

- **Legacy scripts** (19): Scripts antiguos reemplazados
- **Migraciones manuales** (15): Pre-Alembic
- **Rutas no usadas** (2): projects.py, scholar_endpoints.py
- **Data backups**: wos_full_database_v2.xlsx (2.9M)

---

## 📊 Estadísticas

| Categoría | Cantidad | Estado |
|-----------|----------|--------|
| Rutas API activas | 22 | ✅ |
| Servicios | 23 | ✅ |
| Migraciones aplicadas | 18 | ✅ |
| Scripts organizados | 106 | ✅ |
| Archivos archivados | 36 | 📦 |
| Archivos en raíz | 3 | ✅ |

---

## 🔗 Enlaces Útiles

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)

---

## 🆘 Soporte

Para problemas o dudas:
1. Revisar logs del servidor
2. Consultar `/docs` (Swagger)
3. Verificar migraciones: `alembic current`
4. Revisar scripts en `/scripts/README.md`

---

**Última actualización**: 2026-01-25
**Estado del proyecto**: ⭐⭐⭐⭐⭐ (5/5) - Limpio y organizado
