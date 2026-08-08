BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 25780df9e4b7

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE profiles (
    id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE source_documents (
    id UUID NOT NULL, 
    ticker VARCHAR(10) NOT NULL, 
    company_name VARCHAR(255) NOT NULL, 
    form_type VARCHAR(20) NOT NULL, 
    filing_date DATE NOT NULL, 
    report_date DATE, 
    accession_number VARCHAR(30) NOT NULL, 
    source_url TEXT NOT NULL, 
    markdown_content TEXT NOT NULL, 
    metadata JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX idx_source_documents_ticker ON source_documents (ticker);

CREATE UNIQUE INDEX idx_source_documents_accession_number ON source_documents (accession_number);

CREATE INDEX idx_source_documents_metadata_gin ON source_documents USING gin (metadata);

CREATE TABLE document_chunks (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    chunk_text TEXT NOT NULL, 
    token_count INTEGER NOT NULL, 
    embedding VECTOR(768), 
    search_vector TSVECTOR, 
    metadata JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES source_documents (id) ON DELETE CASCADE
);

CREATE INDEX idx_document_chunks_document_id ON document_chunks (document_id);

CREATE INDEX idx_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_document_chunks_search_vector_gin ON document_chunks USING gin (search_vector);

CREATE INDEX idx_document_chunks_metadata_gin ON document_chunks USING gin (metadata);

CREATE OR REPLACE FUNCTION document_chunks_search_vector_update() RETURNS trigger AS $$
    BEGIN
      NEW.search_vector := to_tsvector('english', coalesce(NEW.chunk_text, ''));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_document_chunks_search_vector_update
    BEFORE INSERT OR UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION document_chunks_search_vector_update();

CREATE TABLE chat_threads (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_threads_user_id ON chat_threads (user_id);

CREATE TABLE chat_messages (
    id UUID NOT NULL, 
    thread_id UUID NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    message_json JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_messages_thread_id ON chat_messages (thread_id);

CREATE TABLE message_citations (
    id UUID NOT NULL, 
    message_id UUID NOT NULL, 
    chunk_id UUID NOT NULL, 
    citation_index INTEGER NOT NULL, 
    excerpt TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE CASCADE, 
    FOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE
);

CREATE INDEX idx_message_citations_message_id ON message_citations (message_id);

CREATE INDEX idx_message_citations_chunk_id ON message_citations (chunk_id);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY;

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY;

ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;

ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own profile" ON profiles
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can manage their own chat threads" ON chat_threads
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage messages in their threads" ON chat_messages
    FOR ALL USING (
      EXISTS (
        SELECT 1 FROM chat_threads
        WHERE chat_threads.id = chat_messages.thread_id
        AND chat_threads.user_id = auth.uid()
      )
    );

CREATE POLICY "Users can manage citations in their threads" ON message_citations
    FOR ALL USING (
      EXISTS (
        SELECT 1 FROM chat_messages
        JOIN chat_threads ON chat_threads.id = chat_messages.thread_id
        WHERE chat_messages.id = message_citations.message_id
        AND chat_threads.user_id = auth.uid()
      )
    );

CREATE POLICY "Authenticated users can read source documents" ON source_documents
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated users can read document chunks" ON document_chunks
    FOR SELECT TO authenticated USING (true);

INSERT INTO alembic_version (version_num) VALUES ('25780df9e4b7') RETURNING alembic_version.version_num;

COMMIT;

