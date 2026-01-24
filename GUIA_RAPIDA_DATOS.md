# Guía Rápida: Gestión de Datos de Publicaciones (Backup/Restore)

Este archivo contiene los comandos rápidos para respaldar, borrar y restaurar la base de datos de publicaciones usando el script `scripts/manage_publications_data.py`.

## 📍 Ubicación
Asegúrate de estar en la carpeta `cecan-backend`:
```bash
cd cecan-backend
```

---

## 1️⃣ Hacer Respaldo (Backup)
**⚠️ SIEMPRE EJECUTA ESTO ANTES DE BORRAR NADA.**

```bash
python scripts/manage_publications_data.py --action backup
```
**Resultado:** Te mostrará una ruta, por ejemplo: `data/backups/publications_backup_20260119_200714.json`. **Copia esa ruta.**

---

## 2️⃣ Borrar Todo (Purge)
Esto borra publicaciones, chunks (RAG), impactos y relaciones con investigadores. Deja la tabla limpia.

```bash
python scripts/manage_publications_data.py --action purge
```
*(Debes escribir "DELETE" para confirmar cuando te lo pida)*

---

## 3️⃣ Restaurar (Restore)
Si necesitas recuperar los datos, usa el archivo generado en el paso 1.

**❌ ERROR COMÚN (No copiar el ejemplo literal):**
```bash
python scripts/manage_publications_data.py --action restore --file "data/backups/EL_ARCHIVO_QUE_BOTA_EL_BACKUP.json"
# Esto fallará porque ese archivo no existe.
```

**✅ FORMA CORRECTA (Usando tu archivo real):**
Reemplaza el nombre del archivo con el que generaste en el paso 1.

```bash
# Ejemplo con el backup que ya tienes generado:
python scripts/manage_publications_data.py --action restore --file "data/backups/publications_backup_20260119_200714.json"
```

---

## 🛠️ Solución de Problemas
Si te dice `File not found`, verifica que:
1. Estás ejecutando el comando desde `cecan-backend`.
2. La ruta del archivo está entre comillas dobles `"`.
3. El archivo realmente existe en la carpeta `data/backups/`.
