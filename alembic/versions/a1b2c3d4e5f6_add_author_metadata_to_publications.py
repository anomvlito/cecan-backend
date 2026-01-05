"""add_author_metadata_to_publications

Revision ID: a1b2c3d4e5f6
Revises: f9281a734123
Create Date: 2026-01-05 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f9281a734123'
branch_labels = None
depends_on = None


def upgrade():
    # Add author_metadata JSON column to publications table
    op.add_column('publications', 
        sa.Column('author_metadata', JSON, nullable=True)
    )


def downgrade():
    # Remove author_metadata column
    op.drop_column('publications', 'author_metadata')
