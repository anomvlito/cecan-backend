-- Fix UserRole enum case mismatch in PostgreSQL
-- Run this SQL directly in your database

-- Step 1: Check current enum values
SELECT enumlabel FROM pg_enum WHERE enumtypid = 'userrole'::regtype ORDER BY enumsortorder;

-- Step 2: Drop and recreate the enum with correct lowercase values
-- WARNING: This requires no users table data or temporary column

-- Alternative safe approach: Add new values and migrate
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'staff';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'pi';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'researcher';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'student';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'editor';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer';
