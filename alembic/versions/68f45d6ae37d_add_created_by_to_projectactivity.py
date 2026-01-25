"""Add created_by to ProjectActivity

Revision ID: 68f45d6ae37d
Revises: fix_enum_case_2026
Create Date: 2026-01-24 22:42:22.752750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68f45d6ae37d'
down_revision: Union[str, Sequence[str], None] = 'fix_enum_case_2026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add created_by field to project_activities for permission tracking."""
    op.add_column('project_activities', sa.Column('created_by', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_project_activities_created_by'), 'project_activities', ['created_by'], unique=False)
    op.create_foreign_key('fk_project_activities_created_by', 'project_activities', 'users', ['created_by'], ['id'])


def downgrade() -> None:
    """Remove created_by field from project_activities."""
    op.drop_constraint('fk_project_activities_created_by', 'project_activities', type_='foreignkey')
    op.drop_index(op.f('ix_project_activities_created_by'), table_name='project_activities')
    op.drop_column('project_activities', 'created_by')
