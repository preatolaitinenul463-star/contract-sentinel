"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('plan_type', sa.Enum('free', 'basic', 'pro', 'enterprise', name='plantype'), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False, default=0),
        sa.Column('reviews_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    
    # Create contracts table
    op.create_table('contracts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('contract_type', sa.Enum('general', 'labor', 'tech', 'nda', 'lease', 'sales', 'service', 'other', name='contracttype'), nullable=False),
        sa.Column('jurisdiction', sa.Enum('CN', 'HK', 'SG', 'US', 'UK', 'OTHER', name='jurisdiction'), nullable=False),
        sa.Column('party_role', sa.Enum('party_a', 'party_b', 'employer', 'employee', 'buyer', 'seller', 'unknown', name='partyrole'), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('uploaded', 'parsing', 'parsed', 'reviewing', 'reviewed', 'error', name='contractstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contracts_file_hash'), 'contracts', ['file_hash'], unique=False)
    op.create_index(op.f('ix_contracts_id'), 'contracts', ['id'], unique=False)
    op.create_index(op.f('ix_contracts_user_id'), 'contracts', ['user_id'], unique=False)
    
    # Create review_results table
    op.create_table('review_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=False),
        sa.Column('risk_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('clauses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('high_risk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('medium_risk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('low_risk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('report_path', sa.String(length=500), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, default=0),
        sa.Column('cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('duration_ms', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_results_contract_id'), 'review_results', ['contract_id'], unique=False)
    op.create_index(op.f('ix_review_results_id'), 'review_results', ['id'], unique=False)
    
    # Create comparison_results table
    op.create_table('comparison_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('contract_a_id', sa.Integer(), nullable=False),
        sa.Column('contract_b_id', sa.Integer(), nullable=False),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('added_count', sa.Integer(), nullable=False, default=0),
        sa.Column('removed_count', sa.Integer(), nullable=False, default=0),
        sa.Column('modified_count', sa.Integer(), nullable=False, default=0),
        sa.Column('risk_increased_count', sa.Integer(), nullable=False, default=0),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('key_changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('report_path', sa.String(length=500), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['contract_a_id'], ['contracts.id'], ),
        sa.ForeignKeyConstraint(['contract_b_id'], ['contracts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comparison_results_id'), 'comparison_results', ['id'], unique=False)
    
    # Create chat_sessions table
    op.create_table('chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('context_type', sa.Enum('contract', 'template', 'web_rag', 'general', name='contexttype'), nullable=False),
        sa.Column('context_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_id'), 'chat_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)
    
    # Create chat_messages table
    op.create_table('chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)
    
    # Create rag_documents table
    op.create_table('rag_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('published_date', sa.DateTime(), nullable=True),
        sa.Column('institution', sa.String(length=200), nullable=True),
        sa.Column('doc_type', sa.String(length=100), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('last_crawled_at', sa.DateTime(), nullable=False),
        sa.Column('etag', sa.String(length=200), nullable=True),
        sa.Column('last_modified', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_documents_content_hash'), 'rag_documents', ['content_hash'], unique=False)
    op.create_index(op.f('ix_rag_documents_id'), 'rag_documents', ['id'], unique=False)
    op.create_index(op.f('ix_rag_documents_source_id'), 'rag_documents', ['source_id'], unique=False)
    op.create_index(op.f('ix_rag_documents_url'), 'rag_documents', ['url'], unique=True)
    
    # Create rag_chunks table with vector column
    op.create_table('rag_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['rag_documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rag_chunks_document_id'), 'rag_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_rag_chunks_id'), 'rag_chunks', ['id'], unique=False)
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('tokens_input', sa.Integer(), nullable=False, default=0),
        sa.Column('tokens_output', sa.Integer(), nullable=False, default=0),
        sa.Column('duration_ms', sa.Integer(), nullable=False, default=0),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('rag_chunks')
    op.drop_table('rag_documents')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('comparison_results')
    op.drop_table('review_results')
    op.drop_table('contracts')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS plantype')
    op.execute('DROP TYPE IF EXISTS contracttype')
    op.execute('DROP TYPE IF EXISTS jurisdiction')
    op.execute('DROP TYPE IF EXISTS partyrole')
    op.execute('DROP TYPE IF EXISTS contractstatus')
    op.execute('DROP TYPE IF EXISTS contexttype')
