"""add_ai_journal_analysis_to_publications

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-05 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add ai_journal_analysis JSON column to publications table
    op.add_column('publications', 
        sa.Column('ai_journal_analysis', JSON, nullable=True)
    )


def downgrade():
    # Remove ai_journal_analysis column
    op.drop_column('publications', 'ai_journal_analysis')
