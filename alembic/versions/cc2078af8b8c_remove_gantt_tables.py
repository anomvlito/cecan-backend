"""remove_gantt_tables

Revision ID: cc2078af8b8c
Revises: 14985a79356b
Create Date: 2026-01-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc2078af8b8c'
down_revision: Union[str, None] = '68f45d6ae37d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove legacy Gantt tables (unused, migrated to project_activities)"""

    # Drop tables in reverse dependency order
    # 1. Drop tables with foreign keys first
    op.drop_table('gantt_alerts')
    op.drop_table('gantt_links')

    # 2. Drop main table
    op.drop_table('gantt_tasks')

    # 3. Drop import logs (no dependencies)
    op.drop_table('gantt_import_logs')


def downgrade() -> None:
    """Recreate Gantt tables if needed (will be empty)"""

    # Import logs
    op.create_table('gantt_import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('records_imported', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('imported_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Gantt tasks
    op.create_table('gantt_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('wp_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('budget_allocated', sa.Float(), nullable=True),
        sa.Column('budget_executed', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['gantt_tasks.id'], ),
        sa.ForeignKeyConstraint(['owner_id'], ['academic_members.id'], ),
        sa.ForeignKeyConstraint(['wp_id'], ['work_packages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Gantt links
    op.create_table('gantt_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['gantt_tasks.id'], ),
        sa.ForeignKeyConstraint(['target_id'], ['gantt_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Gantt alerts
    op.create_table('gantt_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_dismissed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['gantt_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
