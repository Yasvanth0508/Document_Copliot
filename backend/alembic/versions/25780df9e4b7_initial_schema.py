"""initial schema

Revision ID: 25780df9e4b7
Revises: 
Create Date: 2026-08-08 17:28:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '25780df9e4b7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create profiles table
    op.create_table(
        'profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create source_documents table
    op.create_table(
        'source_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('form_type', sa.String(length=20), nullable=False),
        sa.Column('filing_date', sa.Date(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=True),
        sa.Column('accession_number', sa.String(length=30), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('markdown_content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_source_documents_ticker', 'source_documents', ['ticker'], unique=False)
    op.create_index('idx_source_documents_accession_number', 'source_documents', ['accession_number'], unique=True)
    op.execute("CREATE INDEX idx_source_documents_metadata_gin ON source_documents USING gin (metadata);")

    # 4. Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['source_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_document_chunks_document_id', 'document_chunks', ['document_id'], unique=False)
    op.execute("CREATE INDEX idx_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);")
    op.execute("CREATE INDEX idx_document_chunks_search_vector_gin ON document_chunks USING gin (search_vector);")
    op.execute("CREATE INDEX idx_document_chunks_metadata_gin ON document_chunks USING gin (metadata);")

    # Trigger for automatic full-text search vector update
    op.execute("""
    CREATE OR REPLACE FUNCTION document_chunks_search_vector_update() RETURNS trigger AS $$
    BEGIN
      NEW.search_vector := to_tsvector('english', coalesce(NEW.chunk_text, ''));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_document_chunks_search_vector_update
    BEFORE INSERT OR UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION document_chunks_search_vector_update();
    """)

    # 5. Create chat_threads table
    op.create_table(
        'chat_threads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_chat_threads_user_id', 'chat_threads', ['user_id'], unique=False)

    # 6. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('thread_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_chat_messages_thread_id', 'chat_messages', ['thread_id'], unique=False)

    # 7. Create message_citations table
    op.create_table(
        'message_citations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('citation_index', sa.Integer(), nullable=False),
        sa.Column('excerpt', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_message_citations_message_id', 'message_citations', ['message_id'], unique=False)
    op.create_index('idx_message_citations_chunk_id', 'message_citations', ['chunk_id'], unique=False)

    # 8. Row-Level Security (RLS) Enablement & Policies
    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;")

    op.execute("""
    CREATE POLICY "Users can manage their own profile" ON profiles
    FOR ALL USING (auth.uid() = id);
    """)
    op.execute("""
    CREATE POLICY "Users can manage their own chat threads" ON chat_threads
    FOR ALL USING (auth.uid() = user_id);
    """)
    op.execute("""
    CREATE POLICY "Users can manage messages in their threads" ON chat_messages
    FOR ALL USING (
      EXISTS (
        SELECT 1 FROM chat_threads
        WHERE chat_threads.id = chat_messages.thread_id
        AND chat_threads.user_id = auth.uid()
      )
    );
    """)
    op.execute("""
    CREATE POLICY "Users can manage citations in their threads" ON message_citations
    FOR ALL USING (
      EXISTS (
        SELECT 1 FROM chat_messages
        JOIN chat_threads ON chat_threads.id = chat_messages.thread_id
        WHERE chat_messages.id = message_citations.message_id
        AND chat_threads.user_id = auth.uid()
      )
    );
    """)
    op.execute("""
    CREATE POLICY "Authenticated users can read source documents" ON source_documents
    FOR SELECT TO authenticated USING (true);
    """)
    op.execute("""
    CREATE POLICY "Authenticated users can read document chunks" ON document_chunks
    FOR SELECT TO authenticated USING (true);
    """)


def downgrade() -> None:
    # Drop policies
    op.execute('DROP POLICY IF EXISTS "Authenticated users can read document chunks" ON document_chunks;')
    op.execute('DROP POLICY IF EXISTS "Authenticated users can read source documents" ON source_documents;')
    op.execute('DROP POLICY IF EXISTS "Users can manage citations in their threads" ON message_citations;')
    op.execute('DROP POLICY IF EXISTS "Users can manage messages in their threads" ON chat_messages;')
    op.execute('DROP POLICY IF EXISTS "Users can manage their own chat threads" ON chat_threads;')
    op.execute('DROP POLICY IF EXISTS "Users can manage their own profile" ON profiles;')

    # Drop trigger & function
    op.execute('DROP TRIGGER IF EXISTS trg_document_chunks_search_vector_update ON document_chunks;')
    op.execute('DROP FUNCTION IF EXISTS document_chunks_search_vector_update();')

    # Drop tables
    op.drop_table('message_citations')
    op.drop_table('chat_messages')
    op.drop_table('chat_threads')
    op.drop_table('document_chunks')
    op.drop_table('source_documents')
    op.drop_table('profiles')
