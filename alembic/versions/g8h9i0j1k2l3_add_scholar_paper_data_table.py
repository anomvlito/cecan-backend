"""add_scholar_paper_data_table

Revision ID: g8h9i0j1k2l3
Revises: d4e5f6g7h8i9
Create Date: 2026-01-21 00:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scholar_paper_data table for embeddings and Scholar API cache."""
    
    # Create enrichment status enum
    enrichment_status_enum = sa.Enum(
        'pending', 'enriched', 'failed', 'not_found', 'rate_limited',
        name='scholarenrichmentstatus'
    )
    enrichment_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create scholar_paper_data table
    op.create_table('scholar_paper_data',
        sa.Column('doi', sa.String(length=255), nullable=False),
        sa.Column('publication_id', sa.Integer(), nullable=True),
        sa.Column('semantic_scholar_id', sa.String(length=50), nullable=True),
        
        # Core Metadata
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('authors', sa.JSON(), nullable=True),
        
        # AI Intelligence
        sa.Column('tldr', sa.Text(), nullable=True),
        sa.Column('abstract', sa.Text(), nullable=True),
        
        # Embeddings (768-dim vector as JSON)
        sa.Column('embedding_vector', sa.JSON(), nullable=True),
        
        # Citation Metrics
        sa.Column('citation_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('influential_citation_count', sa.Integer(), nullable=True, server_default='0'),
        
        # Citation Intelligence
        sa.Column('intent_breakdown', sa.JSON(), nullable=True),
        sa.Column('smart_citations', sa.JSON(), nullable=True),
        
        # Reference Graph
        sa.Column('reference_nodes', sa.JSON(), nullable=True),
        sa.Column('reference_links', sa.JSON(), nullable=True),
        
        # Enrichment Control
        sa.Column('enrichment_status', enrichment_status_enum, nullable=False, server_default='pending'),
        sa.Column('last_enriched_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Audit
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        
        # Constraints
        sa.ForeignKeyConstraint(['publication_id'], ['publications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('doi')
    )
    
    # Create indexes
    op.create_index(op.f('ix_scholar_paper_data_doi'), 'scholar_paper_data', ['doi'], unique=False)
    op.create_index(op.f('ix_scholar_paper_data_publication_id'), 'scholar_paper_data', ['publication_id'], unique=False)
    op.create_index(op.f('ix_scholar_paper_data_semantic_scholar_id'), 'scholar_paper_data', ['semantic_scholar_id'], unique=True)
    op.create_index(op.f('ix_scholar_paper_data_enrichment_status'), 'scholar_paper_data', ['enrichment_status'], unique=False)


def downgrade() -> None:
    """Drop scholar_paper_data table."""
    op.drop_index(op.f('ix_scholar_paper_data_enrichment_status'), table_name='scholar_paper_data')
    op.drop_index(op.f('ix_scholar_paper_data_semantic_scholar_id'), table_name='scholar_paper_data')
    op.drop_index(op.f('ix_scholar_paper_data_publication_id'), table_name='scholar_paper_data')
    op.drop_index(op.f('ix_scholar_paper_data_doi'), table_name='scholar_paper_data')
    op.drop_table('scholar_paper_data')
    
    # Drop enum
    op.execute('DROP TYPE IF EXISTS scholarenrichmentstatus')
