"""fix_userrole_enum_case_consistency

Revision ID: fix_enum_case_2026
Revises: 14985a79356b
Create Date: 2026-01-23

This migration fixes the UserRole enum to use consistent lowercase values.
Old values (ADMIN, EDITOR, VIEWER) are replaced with lowercase equivalents.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'fix_enum_case_2026'
down_revision: Union[str, Sequence[str], None] = '14985a79356b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Standardize UserRole enum to lowercase.
    
    Strategy:
    1. Add lowercase versions of uppercase values
    2. Update existing user records to use lowercase
    3. Remove uppercase values (PostgreSQL limitation: can't remove enum values easily)
    """
    
    # Step 1: Add lowercase versions if they don't exist
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'editor'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer'")
    
    # Step 2: Update existing users to use lowercase values
    op.execute("""
        UPDATE users 
        SET role = 'admin' 
        WHERE role = 'ADMIN'
    """)
    
    op.execute("""
        UPDATE users 
        SET role = 'editor' 
        WHERE role = 'EDITOR'
    """)
    
    op.execute("""
        UPDATE users 
        SET role = 'viewer' 
        WHERE role = 'VIEWER'
    """)
    
    # Note: PostgreSQL doesn't allow removing enum values without recreating the type
    # The old uppercase values (ADMIN, EDITOR, VIEWER) will remain in the enum but unused
    # This is safe and doesn't affect functionality


def downgrade() -> None:
    """
    Revert to uppercase values.
    """
    op.execute("""
        UPDATE users 
        SET role = 'ADMIN' 
        WHERE role = 'admin'
    """)
    
    op.execute("""
        UPDATE users 
        SET role = 'EDITOR' 
        WHERE role = 'editor'
    """)
    
    op.execute("""
        UPDATE users 
        SET role = 'VIEWER' 
        WHERE role = 'viewer'
    """)
