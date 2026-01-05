"""add quartile column

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-05 03:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'quartile' column to publications table
    op.add_column('publications', sa.Column('quartile', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_publications_quartile'), 'publications', ['quartile'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_publications_quartile'), table_name='publications')
    op.drop_column('publications', 'quartile')
