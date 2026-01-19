"""add_gantt_management_tables

Revision ID: 91639dd06599
Revises: 01ef700ffabc
Create Date: 2026-01-18 09:22:53.563982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '91639dd06599'
down_revision: Union[str, Sequence[str], None] = '01ef700ffabc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Gantt management tables."""

    # Create enum types first
    gantt_task_status = sa.Enum(
        'PENDING', 'IN_PROGRESS', 'LATE', 'COMPLETED', 'ON_HOLD',
        name='gantttaskstatus'
    )
    gantt_alert_type = sa.Enum(
        'PREVENTIVE', 'LATE', 'FINANCIAL_DISCREPANCY', 'MILESTONE_RISK',
        name='ganttalerttype'
    )

    # Create gantt_import_logs table
    op.create_table('gantt_import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wp_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('tasks_created', sa.Integer(), nullable=True),
        sa.Column('tasks_updated', sa.Integer(), nullable=True),
        sa.Column('errors_count', sa.Integer(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('imported_by', sa.Integer(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['imported_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['wp_id'], ['work_packages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gantt_import_logs_id'), 'gantt_import_logs', ['id'], unique=False)

    # Create gantt_tasks table
    op.create_table('gantt_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('wp_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('wbs_code', sa.String(length=50), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('budget_allocated', sa.Float(), nullable=True),
        sa.Column('budget_executed', sa.Float(), nullable=True),
        sa.Column('status', gantt_task_status, nullable=False, server_default='PENDING'),
        sa.Column('task_type', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('is_readonly', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['owner_id'], ['academic_members.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['gantt_tasks.id'], ),
        sa.ForeignKeyConstraint(['wp_id'], ['work_packages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gantt_tasks_id'), 'gantt_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_gantt_tasks_parent_id'), 'gantt_tasks', ['parent_id'], unique=False)
    op.create_index(op.f('ix_gantt_tasks_wp_id'), 'gantt_tasks', ['wp_id'], unique=False)

    # Create gantt_alerts table
    op.create_table('gantt_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', gantt_alert_type, nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('budget_variance', sa.Float(), nullable=True),
        sa.Column('progress_variance', sa.Float(), nullable=True),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=True),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['gantt_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gantt_alerts_id'), 'gantt_alerts', ['id'], unique=False)

    # Create gantt_links table
    op.create_table('gantt_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('link_type', sa.String(length=10), nullable=True),
        sa.Column('lag', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['gantt_tasks.id'], ),
        sa.ForeignKeyConstraint(['target_id'], ['gantt_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gantt_links_id'), 'gantt_links', ['id'], unique=False)


def downgrade() -> None:
    """Drop Gantt management tables."""
    op.drop_index(op.f('ix_gantt_links_id'), table_name='gantt_links')
    op.drop_table('gantt_links')
    op.drop_index(op.f('ix_gantt_alerts_id'), table_name='gantt_alerts')
    op.drop_table('gantt_alerts')
    op.drop_index(op.f('ix_gantt_tasks_wp_id'), table_name='gantt_tasks')
    op.drop_index(op.f('ix_gantt_tasks_parent_id'), table_name='gantt_tasks')
    op.drop_index(op.f('ix_gantt_tasks_id'), table_name='gantt_tasks')
    op.drop_table('gantt_tasks')
    op.drop_index(op.f('ix_gantt_import_logs_id'), table_name='gantt_import_logs')
    op.drop_table('gantt_import_logs')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS gantttaskstatus')
    op.execute('DROP TYPE IF EXISTS ganttalerttype')
