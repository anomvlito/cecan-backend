-- Script to clean up duplicate enum values in userrole
-- This removes the uppercase duplicates (ADMIN, EDITOR, VIEWER) and keeps lowercase

-- First, update any existing users that might have uppercase values
UPDATE users SET role = 'admin' WHERE role = 'ADMIN';
UPDATE users SET role = 'editor' WHERE role = 'EDITOR';
UPDATE users SET role = 'viewer' WHERE role = 'VIEWER';

-- Now we need to recreate the enum without duplicates
-- PostgreSQL doesn't allow removing enum values directly, so we:
-- 1. Create a new enum with correct values
-- 2. Alter the column to use the new enum
-- 3. Drop the old enum

-- Create new clean enum
CREATE TYPE userrole_new AS ENUM (
    'super_admin',
    'admin',
    'staff',
    'pi',
    'researcher',
    'student',
    'editor',
    'viewer'
);

-- Update the users table to use the new enum
ALTER TABLE users
    ALTER COLUMN role TYPE userrole_new
    USING role::text::userrole_new;

-- Drop the old enum
DROP TYPE userrole;

-- Rename the new enum to the original name
ALTER TYPE userrole_new RENAME TO userrole;

-- Verify the cleanup
SELECT DISTINCT role FROM users ORDER BY role;
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'userrole'::regtype ORDER BY enumlabel;
