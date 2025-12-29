-- Script de diagnóstico SQL para verificar datos de métricas
-- Ejecutar en la base de datos cecan.db

-- 1. Verificar que la columna existe
PRAGMA table_info(publicaciones);

-- 2. Contar cuántas publicaciones tienen metrics_data
SELECT 
    COUNT(*) as total_publicaciones,
    COUNT(metrics_data) as con_metrics_data,
    COUNT(metrics_last_updated) as con_fecha_actualizacion
FROM publicaciones;

-- 3. Ver ejemplos de publicaciones con métricas
SELECT 
    id,
    titulo,
    metrics_data,
    metrics_last_updated,
    doi_verification_status
FROM publicaciones 
WHERE metrics_data IS NOT NULL 
LIMIT 5;

-- 4. Ver el tipo de dato que tiene metrics_data
SELECT 
    id,
    typeof(metrics_data) as tipo_dato,
    length(metrics_data) as longitud,
    substr(metrics_data, 1, 100) as preview
FROM publicaciones
WHERE metrics_data IS NOT NULL
LIMIT 3;
