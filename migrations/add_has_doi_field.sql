-- Migration: Add has_doi field to publications table
-- This adds a pre-computed boolean field for performance optimization
-- Run this with: psql -U cecan_user -d cecan_db -f add_has_doi_field.sql

-- Step 1: Add column (if not exists)
ALTER TABLE publications 
ADD COLUMN IF NOT EXISTS has_doi BOOLEAN DEFAULT FALSE NOT NULL;

-- Step 2: Create index for performance
CREATE INDEX IF NOT EXISTS ix_publications_has_doi 
ON publications(has_doi);

-- Step 3: Backfill existing data
UPDATE publications
SET has_doi = (
    canonical_doi IS NOT NULL 
    OR (url IS NOT NULL AND (url LIKE '%10.%' OR url LIKE '%doi.org%'))
)
WHERE has_doi = FALSE;

-- Step 4: Show results
SELECT 
    COUNT(*) AS total_publications,
    SUM(CASE WHEN has_doi THEN 1 ELSE 0 END) AS with_doi,
    SUM(CASE WHEN NOT has_doi THEN 1 ELSE 0 END) AS without_doi
FROM publications;
