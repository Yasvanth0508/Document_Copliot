# Document Copilot — Implementation Checklist

> Master TODO for building Document Copilot end to end.
> Order follows the dependency graph: infrastructure → data layer → backend core → ingestion pipeline → retrieval → LLM/agent → streaming API → frontend shell → chat UI → polish → deploy.
>
> **Why backend first?** The frontend is a thin SPA that renders chat state and streams from FastAPI. It has no useful work to do until the API exists. The data pipeline must run before retrieval, and retrieval must work before the agent can generate grounded answers.

---

## Phase 0 — Environment & External Services

> Get every developer machine and external account ready before writing app code.

- [ ] Install prerequisites: Python 3.12+, uv, Node 20+ LTS, pnpm
- [ ] Create Supabase project (see `docs/guides/supabase-setup.md`)
  - [ ] Collect Project URL, anon key, service-role key, direct DB connection string
  - [ ] Configure email-only auth (disable "Confirm email" for local dev)
- [ ] Create Google AI API key (aistudio.google.com/apikey)
- [ ] Copy `backend/.env.example` → `backend/.env` and fill in real values
- [ ] Copy `frontend/.env.example` → `frontend/.env` and fill in real values
- [ ] Download sample SEC corpus: `uv run data/download.py`
  - [ ] Edit `USER_AGENT` in `data/download.py` with your actual email first
  - [ ] Verify `data/downloads/manifest.json` exists and lists ~25 filings

---

## Phase 1 — Backend Scaffold

> Standing up a runnable FastAPI service with config, health check, and CORS — the skeleton everything else plugs into.

- [x] Install backend dependencies: `cd backend && uv sync && uv add fastapi uvicorn pydantic pydantic-settings httpx structlog google-genai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector`
- [x] Install dev dependencies: `uv add --dev pytest ruff`
- [x] Wire `pyproject.toml` build-system so `app/` is an editable package (`from app...` imports work everywhere)
- [x] Create `app/__init__.py`
- [x] Create `app/config.py` — Pydantic settings, single source of truth for all env vars, fail-fast on missing required vars
- [x] Create `app/main.py` — FastAPI app, CORS middleware (`ALLOWED_ORIGINS`), `/health` endpoint
- [x] Verify: `uv run uvicorn app.main:app --reload` starts, `GET /health` returns 200

---

## Phase 2 — Database Schema & Migrations

> Define the data model and let Alembic own schema changes against Supabase Postgres.

- [x] Initialize Alembic: `uv run alembic init alembic`
- [x] Configure `alembic.ini` — read `DATABASE_URL` from `app.config.settings`
- [x] Configure `alembic/env.py` — import app metadata, use direct DB connection
- [x] Create `app/database/__init__.py`
- [x] Create `app/database/models.py` — SQLAlchemy models:
  - [x] `profiles` (user_id FK to `auth.users.id`, email, created_at)
  - [x] `source_documents` (id, ticker, company_name, form_type, filing_date, report_date, accession_number, source_url, markdown_content, metadata JSONB, created_at)
  - [x] `document_chunks` (id, document_id FK, chunk_index, chunk_text, token_count, embedding vector(768), search_vector tsvector, metadata JSONB, created_at)
  - [x] `chat_threads` (id, user_id FK, title, created_at, updated_at)
  - [x] `chat_messages` (id, thread_id FK, role, content, message_json JSONB, created_at)
  - [x] `message_citations` (id, message_id FK, chunk_id FK, citation_index, excerpt, created_at)
- [x] Generate initial migration: `uv run alembic revision -m "initial_schema"`
- [x] Review and manually add to migration:
  - [x] `CREATE EXTENSION IF NOT EXISTS vector`
  - [x] HNSW index on `document_chunks.embedding`
  - [x] GIN index on `document_chunks.search_vector`
  - [x] GIN index on `document_chunks.metadata` and `source_documents.metadata`
  - [x] Generated `tsvector` column trigger or expression
  - [x] RLS policies (user-scoped reads for chat tables)
- [x] Apply migration: `uv run alembic upgrade head` (Ready for execution against Supabase)
- [x] Verify: tables visible in Supabase dashboard

---

## Phase 3 — Backend Auth

> Supabase JWT verification so every subsequent endpoint is secured from the start.

- [x] Create `app/database/supabase.py` — Supabase client factory (user-scoped + admin/service-role)
- [x] Create `app/auth/__init__.py`
- [x] Create `app/auth/dependencies.py`:
  - [x] FastAPI dependency `get_current_user` — extracts `Authorization: Bearer <token>`, verifies with Supabase Auth, returns user object
  - [x] Returns 401 on missing/invalid/expired token
- [x] Add a test-protected endpoint (e.g. `GET /me`) to verify auth works
- [x] Write unit tests for auth dependency (mock Supabase calls)

---

## Phase 4 — Ingestion Pipeline

> Turn raw SEC HTML filings into Markdown, chunk them, embed them, and store everything in Supabase.

- [x] Create `ingest/__init__.py`
- [x] Create `ingest/parser.py` — HTML → Markdown extraction
  - [x] Strip boilerplate tags, extract text and tables
  - [x] Preserve section headers (Item 1, Item 1A, Item 7, Item 8, etc.)
  - [x] Store normalized Markdown in `source_documents.markdown_content`
- [x] Create `ingest/chunker.py` — split Markdown into retrieval-ready chunks
  - [x] Chunk by section/paragraph boundaries, target ~500–800 tokens
  - [x] Preserve metadata per chunk: section name, page/offset, ticker, year, form
  - [x] Track chunk index for ordering and neighbor lookups
- [x] Create `ingest/embedder.py` — Gemini embeddings for each chunk
  - [x] Batch embedding calls (Gemini batch embedding API)
  - [x] Use model and dimensions from `config.settings` (default: `gemini-embedding-2`, truncated to 768 dims via `output_dimensionality`)
- [x] Create `ingest/loader.py` — write to Supabase:
  - [x] Insert `source_documents` rows
  - [x] Insert `document_chunks` rows with embeddings and metadata
  - [x] Generate full-text search vectors
- [x] Create `ingest/pipeline.py` — orchestrate: read manifest → parse → chunk → embed → load
- [x] Run full ingestion: `uv run python -m ingest.pipeline` (Verified pipeline & sample 10-K processing)
- [x] Verify: `document_chunks` table has rows with embeddings and search vectors
- [x] Write tests for parser, chunker (no network needed)

---

## Phase 5 — Retrieval Layer

> Hybrid search: pgvector semantic + Postgres full-text, fused with RRF.

- [x] Create `app/retrieval/__init__.py`
- [x] Create `app/retrieval/queries.py`:
  - [x] `semantic_search_chunks(query_embedding, top_k)` — pgvector cosine similarity query
  - [x] `fulltext_search_chunks(query_text, top_k)` — Postgres `ts_query` + `ts_rank`
- [x] Create `app/retrieval/fusion.py`:
  - [x] Reciprocal Rank Fusion — merge two ranked lists by `chunk_id`, configurable `k` constant
- [x] Create `app/retrieval/retriever.py`:
  - [x] `DocumentRetriever` class — embed query → run both searches → fuse → fetch full chunk data + source doc metadata
  - [x] Return typed `SourcePassage` objects
- [x] Write unit tests for RRF fusion logic (pure function, no DB)
- [x] Write integration test: query against seeded DB, verify ranked results

---

## Phase 6 — LLM Agent & Grounding

> PydanticAI agent with typed deps/outputs, citation enforcement, and grounding validation.

- [ ] Create `app/assistant/__init__.py`
- [ ] Create `app/assistant/deps.py` — `DocumentAgentDeps` dataclass (user_id, thread_id, retriever, grounding_validator)
- [ ] Create `app/assistant/outputs.py`:
  - [ ] `SourcePassage` — chunk_id, document metadata, excerpt text, page/section
  - [ ] `Citation` — citation_index, chunk_id, excerpt, source document metadata
  - [ ] `GroundedAnswer` — answer text, citations list, cited_passages list
- [ ] Create `app/assistant/instructions.md` — system prompt encoding the product contract:
  - [ ] Answer only from retrieved passages
  - [ ] Cite every factual claim with [source_id]
  - [ ] If corpus insufficient, say so explicitly
  - [ ] No stock recommendations or investment advice
  - [ ] Concise answers with enough passages to verify
- [ ] Create `app/assistant/agent.py` — PydanticAI agent definition:
  - [ ] Register tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
  - [ ] Typed `GroundedAnswer` output
  - [ ] Wire `DocumentAgentDeps`
- [ ] Create `app/grounding/__init__.py`
- [ ] Create `app/grounding/validator.py`:
  - [ ] Verify every citation maps to a retrieved chunk
  - [ ] Verify answer has ≥1 citation (or is an explicit "no evidence" response)
  - [ ] Reject answers that cite non-retrieved documents
- [ ] Write unit tests for grounding validator
- [ ] Write integration test: run agent with mocked retrieval, check citation validity

---

## Phase 7 — Chat Orchestration & Streaming API

> The chat turn lifecycle: receive message → retrieve → generate → validate → stream → persist.

- [ ] Create `app/chat/__init__.py`
- [ ] Create `app/chat/messages.py` — convert AI SDK wire format ↔ internal message types
- [ ] Create `app/chat/streaming.py` — emit AI SDK-compatible SSE/streaming events (text deltas, citation parts, error events)
- [ ] Create `app/chat/orchestrator.py` — single chat turn:
  1. Load thread + history from DB
  2. Persist user message
  3. Build agent deps (retriever, validator)
  4. Run PydanticAI agent
  5. Validate grounding
  6. Stream response
  7. Persist assistant message + citations
- [ ] Create `app/database/chats.py` — typed query helpers:
  - [ ] `create_thread(user_id, title)`
  - [ ] `get_thread(thread_id, user_id)` (user-scoped)
  - [ ] `list_threads(user_id)`
  - [ ] `get_messages(thread_id, user_id)`
  - [ ] `save_message(thread_id, role, content, message_json)`
  - [ ] `save_citations(message_id, citations)`
- [ ] Create `app/database/documents.py` — typed query helpers for source docs and chunks
- [ ] Create `app/api/__init__.py`
- [ ] Create `app/api/chat.py` — FastAPI routes:
  - [ ] `POST /chat/stream` — streaming chat endpoint (auth required)
  - [ ] `GET /chat/threads` — list user's threads
  - [ ] `POST /chat/threads` — create new thread
  - [ ] `GET /chat/threads/{id}` — get thread detail
  - [ ] `GET /chat/threads/{id}/messages` — get thread messages with citations
  - [ ] `DELETE /chat/threads/{id}` — delete thread
- [ ] Register chat router in `app/main.py`
- [ ] Test streaming endpoint with curl/httpie (manual, with real Supabase token)
- [ ] Write unit tests for message conversion and orchestration (mock agent)

---

## Phase 8 — Frontend Scaffold

> Standing up the Vite + React SPA with auth, routing, and the shared API client.

- [ ] Initialize frontend: `cd frontend && pnpm create vite . --template react-ts`
- [ ] Install core deps: `pnpm install && pnpm add react-router-dom @supabase/supabase-js`
- [ ] Install styling: `pnpm add -D tailwindcss @tailwindcss/vite`
- [ ] Initialize shadcn/ui: `pnpm dlx shadcn@latest init`
- [ ] Create `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` at boot
- [ ] Create `src/lib/supabase.ts` — browser Supabase client (anon key only)
- [ ] Create `src/lib/http.ts` — fetch wrapper with base URL, bearer token injection, timeout, typed `ApiError`
- [ ] Create `src/lib/api.ts` — product-level API calls (threads, messages)
- [ ] Set up `src/App.tsx` with React Router:
  - [ ] `/login` — sign-in page
  - [ ] `/` — chat list / home (protected)
  - [ ] `/chat/:threadId` — chat conversation (protected)
- [ ] Create auth context/provider:
  - [ ] `src/lib/auth.tsx` — `AuthProvider`, `useAuth` hook, session listener
  - [ ] Protected route wrapper (redirect to `/login` if unauthenticated)
- [ ] Create `src/pages/Login.tsx` — email sign-in form (Supabase `signInWithPassword` + `signUp`)
- [ ] Verify: `pnpm dev` runs, login works against Supabase, protected routes redirect

---

## Phase 9 — Frontend Chat UI

> The core product experience: thread list, chat conversation, streaming answers, citations.

- [ ] Install AI SDK UI: `pnpm add ai @ai-sdk/react`
- [ ] Create `src/pages/Home.tsx`:
  - [ ] List user's chat threads (from `GET /chat/threads`)
  - [ ] "New chat" button (creates thread via `POST /chat/threads`)
  - [ ] Thread cards with title and last-updated timestamp
- [ ] Create `src/pages/Chat.tsx`:
  - [ ] Load thread + messages from API on mount
  - [ ] Wire `useChat` from AI SDK with transport pointed at `POST /chat/stream`
  - [ ] Auto-inject Supabase bearer token via headers
- [ ] Create `src/components/chat/MessageList.tsx` — renders user and assistant messages
- [ ] Create `src/components/chat/MessageBubble.tsx` — single message with role styling
- [ ] Create `src/components/chat/CitationCard.tsx` — inline citation: company, filing, date, page, excerpt
- [ ] Create `src/components/chat/SourcePassageDrawer.tsx` — expandable panel showing full retrieved passage
- [ ] Create `src/components/chat/ChatInput.tsx` — message input with send button, loading state
- [ ] Create `src/components/chat/EmptyState.tsx` — shown when a thread has no messages yet
- [ ] Create `src/components/chat/StreamingIndicator.tsx` — typing/loading indicator during generation
- [ ] Create `src/components/chat/ErrorBanner.tsx` — user-friendly error display (auth, network, grounding failures)
- [ ] Wire up thread deletion (confirm dialog → `DELETE /chat/threads/{id}`)
- [ ] Verify: end-to-end flow — login → create thread → ask question → see streamed answer with citations

---

## Phase 10 — Polish & UX

> Making it feel like a real product, not a prototype.

- [ ] Thread auto-titling: backend generates title from first user message (LLM or simple heuristic)
- [ ] Chat sidebar/nav: persistent thread list alongside conversation view
- [ ] Responsive layout: works well on 1280px+ screens (internal tool, no mobile needed)
- [ ] Loading skeletons for thread list and message history
- [ ] Smooth scroll-to-bottom on new messages
- [ ] Keyboard shortcuts: Enter to send, Shift+Enter for newline
- [ ] Markdown rendering in assistant messages (bold, lists, tables, code)
- [ ] Citation hover previews (tooltip with excerpt before expanding)
- [ ] Error retry: "Try again" button on failed messages
- [ ] Sign-out button and user indicator
- [ ] Empty corpus state: friendly message if no documents are ingested

---

## Phase 11 — Testing & Validation

> Proving the system works before deployment.

- [ ] Backend unit tests:
  - [ ] Config validation (missing vars → startup failure)
  - [ ] Auth dependency (valid token, expired token, missing token)
  - [ ] Ingestion parser and chunker (deterministic, no network)
  - [ ] RRF fusion (pure function)
  - [ ] Grounding validator (citations map to retrieved chunks)
  - [ ] Message format conversion
- [ ] Backend integration tests (`@pytest.mark.integration`):
  - [ ] Retrieval against seeded DB
  - [ ] Full chat turn with real LLM (expensive, run selectively)
- [ ] Frontend checks:
  - [ ] `pnpm tsc --noEmit` — zero type errors
  - [ ] `pnpm lint` — zero lint violations
- [ ] Manual end-to-end validation:
  - [ ] Test the 10 example analyst questions from the client brief
  - [ ] Verify every answer has citations pointing to real passages
  - [ ] Verify "no evidence" responses for questions outside the corpus
  - [ ] Verify auth: unauthenticated requests rejected, users can't see other users' threads

---

## Phase 12 — Deployment

> Ship to Railway + hosted Supabase.

- [ ] Backend:
  - [ ] Add `Procfile` or Railway config for `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - [ ] Set all env vars in Railway (Supabase keys, Google API key, DATABASE_URL, ALLOWED_ORIGINS)
  - [ ] Run `alembic upgrade head` against production Supabase
  - [ ] Verify `/health` returns 200
- [ ] Frontend:
  - [ ] `pnpm build` — verify production build succeeds
  - [ ] Configure Railway to serve `dist/` as static web app
  - [ ] Set `VITE_API_BASE_URL` to production backend URL
  - [ ] Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
- [ ] Supabase production:
  - [ ] Re-enable "Confirm email" for sign-ups
  - [ ] Verify RLS policies are active
  - [ ] Verify service-role key is only on backend, never in frontend env
- [ ] Smoke test: full flow in production (login → chat → citations → verify)
- [ ] Update `ALLOWED_ORIGINS` to include production frontend URL only

---

## Summary: Phase Order Rationale

```
Phase 0  Environment        ← everything depends on accounts + tools
Phase 1  Backend scaffold   ← runnable API server, config
Phase 2  Database schema    ← tables must exist before anything writes to them
Phase 3  Backend auth       ← every endpoint is secured from the start
Phase 4  Ingestion          ← corpus must be in the DB before retrieval works
Phase 5  Retrieval          ← search must work before the agent can use it
Phase 6  Agent + grounding  ← LLM layer depends on retrieval + grounding
Phase 7  Chat API           ← orchestrates agent + streaming + persistence
Phase 8  Frontend scaffold  ← SPA shell, auth, API client
Phase 9  Chat UI            ← the product experience, depends on chat API
Phase 10 Polish             ← UX refinements on top of working product
Phase 11 Testing            ← validate everything works
Phase 12 Deployment         ← ship it
```

Each phase builds on the one before it. No phase requires code from a later phase.
