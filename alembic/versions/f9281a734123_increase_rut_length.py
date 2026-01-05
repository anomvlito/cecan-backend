
"""increase_rut_length

Revision ID: f9281a734123
Revises: e819df785656
Create Date: 2026-01-03 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9281a734123'
down_revision = 'e819df785656'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('students', 'rut',
               existing_type=sa.String(length=20),
               type_=sa.String(length=50),
               existing_nullable=True)


def downgrade():
    op.alter_column('students', 'rut',
               existing_type=sa.String(length=50),
               type_=sa.String(length=20),
               existing_nullable=True)
