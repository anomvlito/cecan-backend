-- Reset completo de la tabla wos_journal_mirror
-- Borra la tabla existente y la recrea con categories como JSONB

-- Paso 1: Eliminar tabla existente
DROP TABLE IF EXISTS wos_journal_mirror CASCADE;

-- Paso 2: Recrear tabla con estructura correcta
CREATE TABLE wos_journal_mirror (
    wos_id INTEGER PRIMARY KEY,           -- El ID de la URL (ej: 1 de journalid/1)
    journal_name TEXT,
    status VARCHAR(50),                   -- Active, Discontinued, etc.
    best_quartile VARCHAR(10),            -- Q1, Q2, Q3, Q4, N/A
    best_ranking_percent VARCHAR(20),     -- Ej: "99.7%"
    jif VARCHAR(20),                      -- Journal Impact Factor (puede ser numérico o 'N/A')
    five_year_jif VARCHAR(20),            -- 5-Year Impact Factor
    issn VARCHAR(20),
    eissn VARCHAR(20),
    categories JSONB,                     -- Array JSON de categorías parseadas (sin "- SCIE")
    ranking_category TEXT,                -- La categoría específica donde obtuvo el mejor ranking
    publisher TEXT,                       -- Nombre del publisher
    country VARCHAR(100),
    full_ranking_raw TEXT,                -- Dump del texto original del ranking para depuración
    source_url TEXT,                      -- URL de origen
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Paso 3: Crear índices para búsqueda ultra-rápida
CREATE INDEX IF NOT EXISTS idx_wos_mirror_issn ON wos_journal_mirror(issn);
CREATE INDEX IF NOT EXISTS idx_wos_mirror_eissn ON wos_journal_mirror(eissn);
CREATE INDEX IF NOT EXISTS idx_wos_mirror_name_lower ON wos_journal_mirror(lower(journal_name));
CREATE INDEX IF NOT EXISTS idx_wos_mirror_categories_gin ON wos_journal_mirror USING GIN (categories);

-- Confirmación
SELECT 'Tabla wos_journal_mirror recreada exitosamente con categories como JSONB' AS status;
