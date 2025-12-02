# 🗄️ Scripts de Migración y Setup CECAN

Esta carpeta contiene todos los scripts para inicializar y migrar la base de datos.

## 📋 Scripts de Inicialización

### Setup Inicial (Primera Vez)
```bash
# 1. Crear tablas base de proyectos
python backend/migrations/seed_database.py

# 2. Crear tablas de investigadores y publicaciones (legacy)
python backend/migrations/migrate_db.py

# 3. Crear tabla de chunks RAG
python backend/migrations/migrate_rag.py
```

### Setup con SQLAlchemy (Nuevo - Recomendado)
```bash
# Crear todas las tablas con ORM
python -m backend.models
```

## 🔄 Scripts de Migración

- **`seed_database.py`** - Inicializa datos base (Proyectos, WPs, Nodos)
- **`migrate_db.py`** - Crea tablas principales (Investigadores, Publicaciones)
- **`migrate_rag.py`** - Crea tabla de chunks para RAG
- **`restore_tables.py`** - Restaura tablas desde backup

## 🧠 Procesamiento de Datos

- **`process_rag.py`** - Procesa publicaciones y genera embeddings

## 📖 Orden de Ejecución Recomendado

### Primera Instalación (Legacy)
```bash
# 1. Datos base
python backend/migrations/seed_database.py

# 2. Tablas principales
python backend/migrations/migrate_db.py

# 3. Sistema RAG
python backend/migrations/migrate_rag.py

# 4. Procesar embeddings (después de sincronizar publicaciones)
python backend/migrations/process_rag.py
```

### Primera Instalación (SQLAlchemy - Nuevo)
```bash
# 1. Crear todas las tablas
python -m backend.models

# 2. Crear usuario admin
python -m backend.auth

# 3. (Opcional) Cargar datos base de proyectos
python backend/migrations/seed_database.py

# 4. Sincronizar datos desde web (desde la API)
POST /api/sync-staff
POST /api/sync-publications

# 5. Procesar embeddings
python backend/migrations/process_rag.py
```

## ⚠️ Precauciones

- **Backup**: Siempre haz backup de `cecan.db` antes de ejecutar migraciones
- **Orden**: Ejecuta los scripts en el orden recomendado
- **Una vez**: La mayoría de estos scripts solo deben ejecutarse una vez
- **Tiempo**: `process_rag.py` puede tomar 20-30 minutos para ~100 publicaciones

## 🔧 Mantenimiento

### Re-procesar RAG
```bash
# Limpiar chunks existentes
python -c "import sqlite3; conn = sqlite3.connect('backend/cecan.db'); conn.execute('DELETE FROM publication_chunks'); conn.commit()"

# Re-procesar
python backend/migrations/process_rag.py
```

### Restaurar Tablas
```bash
python backend/migrations/restore_tables.py
```

---

**Importante**: Ejecuta estos scripts desde la raíz del proyecto.
