#!/bin/bash
# Quick fix for alembic multiple heads

echo "🔧 Fixing Alembic multiple heads..."

# Remove our migration temporarily
rm alembic/versions/d4e5f6a7b8c9_add_student_document_fields.py

# Check heads
echo "Current heads:"
alembic heads

# Apply all existing migrations
alembic upgrade heads

# Now recreate our migration using autogenerate (will properly chain)
alembic revision --autogenerate -m "add_student_document_fields"

echo "✅ Migration chain fixed. Now run: alembic upgrade head"
