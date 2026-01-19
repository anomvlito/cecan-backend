"""add_scientific_projects_tables

Revision ID: f72778819959
Revises: 91639dd06599
Create Date: 2026-01-18 23:53:44.642794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f72778819959'
down_revision: Union[str, Sequence[str], None] = '91639dd06599'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Scientific Projects tables."""

    # Create enums
    work_package_type = sa.Enum(
        'WP1', 'WP2', 'WP3', 'WP4', 'OUTREACH', 'TRAINING', 'GOVERNANCE',
        name='workpackagetype'
    )
    project_status_type = sa.Enum(
        'DRAFT', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED',
        name='projectstatustype'
    )
    activity_status_type = sa.Enum(
        'PENDING', 'IN_PROGRESS', 'DONE', 'BLOCKED',
        name='activitystatustype'
    )

    # Create scientific_projects table
    op.create_table('scientific_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('work_package', work_package_type, nullable=False),
        sa.Column('grant_type', sa.String(length=100), nullable=True),
        sa.Column('pi_id', sa.Integer(), nullable=True),
        sa.Column('pi_name', sa.String(length=200), nullable=True),
        sa.Column('years_covered', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('budget_allocated', sa.Float(), nullable=True, server_default='0'),
        sa.Column('budget_executed', sa.Float(), nullable=True, server_default='0'),
        sa.Column('currency', sa.String(length=10), nullable=True, server_default='CLP'),
        sa.Column('status', project_status_type, nullable=True, server_default='DRAFT'),
        sa.Column('progress', sa.Float(), nullable=True, server_default='0'),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['pi_id'], ['academic_members.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scientific_projects_id'), 'scientific_projects', ['id'], unique=False)
    op.create_index(op.f('ix_scientific_projects_code'), 'scientific_projects', ['code'], unique=True)

    # Create project_activities table
    op.create_table('project_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('start_month', sa.Date(), nullable=True),
        sa.Column('end_month', sa.Date(), nullable=True),
        sa.Column('status', activity_status_type, nullable=True, server_default='PENDING'),
        sa.Column('progress', sa.Float(), nullable=True, server_default='0'),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['scientific_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_activities_id'), 'project_activities', ['id'], unique=False)
    op.create_index(op.f('ix_project_activities_project_id'), 'project_activities', ['project_id'], unique=False)


def downgrade() -> None:
    """Drop Scientific Projects tables."""
    op.drop_index(op.f('ix_project_activities_project_id'), table_name='project_activities')
    op.drop_index(op.f('ix_project_activities_id'), table_name='project_activities')
    op.drop_table('project_activities')

    op.drop_index(op.f('ix_scientific_projects_code'), table_name='scientific_projects')
    op.drop_index(op.f('ix_scientific_projects_id'), table_name='scientific_projects')
    op.drop_table('scientific_projects')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS activitystatustype')
    op.execute('DROP TYPE IF EXISTS projectstatustype')
    op.execute('DROP TYPE IF EXISTS workpackagetype')
