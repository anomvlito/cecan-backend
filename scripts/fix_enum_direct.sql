-- Direct SQL fix for UserRole enum case consistency
-- Execute this file directly with psql (NOT through Alembic)
-- 
-- Usage:
--   psql -h localhost -U cecan_user -d cecan_db -f fix_enum_direct.sql

-- Step 1: Add lowercase enum values (must be outside transaction)
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'editor';  
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer';

-- Step 2: Update existing users to use lowercase
UPDATE users SET role = 'admin' WHERE role = 'ADMIN';
UPDATE users SET role = 'editor' WHERE role = 'EDITOR';
UPDATE users SET role = 'viewer' WHERE role = 'VIEWER';

-- Step 3: Verify the changes
SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role;

-- Step 4: Show all enum values
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'userrole'::regtype ORDER BY enumsortorder;
