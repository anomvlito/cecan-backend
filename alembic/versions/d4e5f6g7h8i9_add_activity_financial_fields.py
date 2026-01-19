"""add_activity_financial_fields

Revision ID: d4e5f6g7h8i9
Revises: f72778819959
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'f72778819959'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add financial control fields to project_activities."""

    # Create payment status enum
    payment_status_type = sa.Enum('PENDING', 'PAID', name='paymentstatustype')
    try:
        payment_status_type.create(op.get_bind(), checkfirst=True)
    except Exception:
        pass # Enum might already exist if migration partially ran

    # Add WP5 to workpackagetype enum
    op.execute("ALTER TYPE workpackagetype ADD VALUE IF NOT EXISTS 'WP5'")

    # Add financial columns to project_activities
    op.add_column('project_activities',
        sa.Column('budget_allocated', sa.Float(), nullable=True, server_default='0')
    )
    op.add_column('project_activities',
        sa.Column('payment_status', payment_status_type, nullable=True, server_default='PENDING')
    )
    op.add_column('project_activities',
        sa.Column('payment_proof_url', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    """Remove financial control fields from project_activities."""

    op.drop_column('project_activities', 'payment_proof_url')
    op.drop_column('project_activities', 'payment_status')
    op.drop_column('project_activities', 'budget_allocated')

    # Drop enum (note: can't easily remove enum value from workpackagetype)
    op.execute('DROP TYPE IF EXISTS paymentstatustype')
