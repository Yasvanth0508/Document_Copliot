# Document Copilot — Backend Service

FastAPI backend service providing authentication, SEC document ingestion, hybrid search retrieval, and grounded AI chat orchestration.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) package manager

## Quick Start

### 1. Environment Setup

Copy `.env.example` to `.env` and fill in your Supabase, Postgres, and Google Gemini API credentials:

```bash
cp .env.example .env
```

### 2. Install Dependencies

Sync dependencies and install the local `app` package:

```bash
uv sync
```

### 3. Run Database Migrations

Apply database migrations to hosted Supabase Postgres:

```bash
uv run alembic upgrade head
```

### 4. Start Development Server

Run FastAPI with hot-reloading enabled:

```bash
uv run uvicorn app.main:app --reload
```

- API Base URL: `http://localhost:8000`
- Health Check: `http://localhost:8000/health`
- Interactive API Docs (Swagger UI): `http://localhost:8000/docs`

## Common Commands

| Action | Command |
| ------ | ------- |
| **Start API Server** | `uv run uvicorn app.main:app --reload` |
| **Apply Migrations** | `uv run alembic upgrade head` |
| **Create Migration** | `uv run alembic revision --autogenerate -m "description"` |
| **Run Tests** | `uv run pytest` |
| **Run Fast Tests (no network/DB)** | `uv run pytest -m "not integration"` |
| **Add Runtime Dependency** | `uv add <package-name>` |
| **Add Dev Dependency** | `uv add --dev <package-name>` |
