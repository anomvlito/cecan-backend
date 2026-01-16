-- Migración para convertir categories de TEXT a JSONB
-- Esto permite guardar arrays de categorías en lugar de strings con separador

-- Paso 1: Agregar columna temporal JSONB
ALTER TABLE wos_journal_mirror ADD COLUMN categories_new JSONB;

-- Paso 2: Migrar datos existentes (convertir string con pipe a array JSON)
UPDATE wos_journal_mirror 
SET categories_new = 
    CASE 
        WHEN categories IS NULL THEN NULL
        WHEN categories LIKE '%|%' THEN 
            -- Múltiples categorías: convertir a array
            to_jsonb(string_to_array(categories, '|'))
        ELSE 
            -- Una sola categoría: crear array con un elemento
            to_jsonb(ARRAY[categories])
    END;

-- Paso 3: Eliminar columna vieja
ALTER TABLE wos_journal_mirror DROP COLUMN categories;

-- Paso 4: Renombrar columna nueva
ALTER TABLE wos_journal_mirror RENAME COLUMN categories_new TO categories;

-- Paso 5: Crear índice GIN para búsquedas rápidas en JSON
CREATE INDEX IF NOT EXISTS idx_wos_mirror_categories_gin ON wos_journal_mirror USING GIN (categories);
