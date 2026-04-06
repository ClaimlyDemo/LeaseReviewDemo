# Lease Review Tool Backend

This repository contains the backend scaffold for the Lease Review Tool prototype described in [PRODUCT_SPEC.md](/Users/kevinwu_new/Desktop/Claimly/Lease%20Review%20Tool/PRODUCT_SPEC.md).

The current scaffold is built around two explicit stages:

- reference ingestion
- lease analysis

It is intentionally backend-first. Frontend work is still out of scope.

## Current Status

What exists now:

- Python package scaffold under `src/lease_review_tool`
- stage-oriented CLI commands
- FastAPI app entrypoint
- PostgreSQL + SQLAlchemy data model scaffold
- `pgvector`-ready embedding column
- PyMuPDF first-pass PDF parsing
- AWS Textract OCR fallback for low-quality PDF pages
- local document parsing hooks for DOCX
- incremental reference-ingestion skeleton
- transient lease-analysis pipeline
- OpenAI-backed normalized summaries during ingestion and analysis preparation
- OpenAI embeddings during ingestion and analysis preparation
- `gpt-5.4` final flagging over retrieved clause evidence

What is still intentionally incomplete:

- production-grade clause segmentation
- robust LLM extraction prompts
- full benchmark logic
- polished rule-artifact generation
- Alembic migration history
- tests

## Stack

- Python 3.13+
- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector
- PyMuPDF
- AWS Textract via boto3
- OpenAI Python SDK
- PyPDF
- python-docx

## Local Setup

### 1. Create a virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

Install the package into the virtual environment so `python3 -m lease_review_tool.cli` resolves reliably (including on macOS with iCloud/Desktop paths, where editable installs can break):

```bash
python3 -m pip install --upgrade pip
python3 -m pip install .
```

Editable install is optional if you change code often; reinstall after edits, or use `run_cli.py` (below):

```bash
python3 -m pip install -e .
```

If you already had the project installed before the PyMuPDF/Textract update, run `python3 -m pip install -e .` again so the new dependencies are available in the current venv.

**CLI entry (pick one):**

- **`python3 -m lease_review_tool.cli …`** — works after `pip install .` or a working `pip install -e .`.
- **`python3 run_cli.py …`** — run from the **repository root** with the same arguments. It prepends `src/` to `sys.path`, so it does not depend on editable `.pth` files or `PYTHONPATH`. Use this whenever you see `ModuleNotFoundError: No module named 'lease_review_tool'`.

Throughout the rest of this document, you can replace `python3 -m lease_review_tool.cli` with `python3 run_cli.py` (still from the repo root).

Progress updates for ingestion and analysis are written to `stderr`, so they remain visible in the terminal without polluting JSON output written to `stdout`.

### 3. Create a local Postgres database

The scaffold expects a PostgreSQL database with `pgvector` available.

First, download Docker and verify installation with ```docker --version```

Then, start a container:
```
docker run -d \
  --name lease-review-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=lease_review_tool \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```


Example local connection string:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/lease_review_tool"
```

When you no longer need the container:
```
docker stop lease-review-pg
docker rm lease-review-pg
```


### 4. Configure environment variables

Create a local `.env` from the template:

```bash
cp .env.example .env
```

Then edit `.env` with your settings. The backend now auto-loads `.env` from the working directory for both CLI and API runs.

Example `.env`:

```bash
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/lease_review_tool"
OPENAI_API_KEY="your-key-here"
OPENAI_EXTRACTION_MODEL="gpt-5.4-mini"
OPENAI_REASONING_MODEL="gpt-5.4"
OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
OPENAI_EMBEDDING_DIMENSIONS="1536"
AWS_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your-aws-access-key"
AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
AWS_SESSION_TOKEN=""
PDF_OCR_QUALITY_THRESHOLD="0.72"
PDF_OCR_RENDER_DPI="200"
REFERENCE_DOCUMENT_DIR="/absolute/path/to/reference/docs"
```

If `OPENAI_API_KEY` is missing, or if the database is unreachable, the ingestion and analysis pipelines will now fail fast with a clear error instead of running in fallback mode.

The `.env` file is auto-loaded by the backend at startup. You do not need to restart the venv after editing `.env`; just rerun the CLI command or restart the API process. If the FastAPI server is already running, restart that process so it picks up the updated environment.

## Initialize the Database

Before ingestion or analysis, create the database schema:

```bash
python3 -m lease_review_tool.cli init-db
```

This command:

- creates the `vector` extension when available
- creates the current SQLAlchemy tables

## Stage 1: Reference Ingestion

Use this stage to ingest one reference lease or a whole directory of reference leases into the persistent knowledge base.

### Ingest a single file

```bash
python3 -m lease_review_tool.cli ingest-reference --path /absolute/path/to/reference-lease.pdf
```

### Ingest a directory

```bash
python3 -m lease_review_tool.cli ingest-reference --path /absolute/path/to/reference-directory
```

### Force reprocessing of an already ingested file

```bash
python3 -m lease_review_tool.cli ingest-reference --path /absolute/path/to/reference-lease.pdf --force
```

What the ingestion stage currently does:

- fingerprints the source file
- parses PDF or DOCX text
- uses PyMuPDF as the first-pass PDF extractor
- sends only low-quality PDF pages to AWS Textract OCR
- filters out obvious non-lease artifacts and low-value OCR/form fragments before clause segmentation
- segments text into clause-like blocks
- classifies clauses into a starter taxonomy
- extracts simple numeric fields
- creates normalized text through the configured extraction model, default `gpt-5.4-mini`
- generates embeddings through the configured embedding model, default `text-embedding-3-small`
- stores reference documents and clauses
- recomputes benchmark profiles
- regenerates human-readable rule artifacts

## Stage 2: Lease Analysis

Use this stage to analyze a user lease against the current knowledge base.

The analyzed lease is treated as transient input and is not persisted in the database in this scaffold.

### Analyze one lease

```bash
python3 -m lease_review_tool.cli analyze-lease --path /absolute/path/to/user-lease.pdf
```

### Write the JSON response to a file

```bash
python3 -m lease_review_tool.cli analyze-lease \
  --path /absolute/path/to/user-lease.pdf \
  --output /absolute/path/to/output.json
```

What the analysis stage currently does:

- parses the uploaded lease
- uses PyMuPDF as the first-pass PDF extractor
- sends only low-quality PDF pages to AWS Textract OCR
- filters out obvious non-lease artifacts and low-value OCR/form fragments before clause segmentation
- segments it into clause-like blocks
- classifies clauses locally
- computes transient embeddings in a batched request with the configured embedding model, default `text-embedding-3-small`
- retrieves comparable reference clauses, benchmark summaries, and rule-artifact evidence locally
- sends candidate clause-evidence packets to `gpt-5.4` for the final flagging decision
- returns up to 10 flagged observations in structured JSON

## After OCR or Segmentation Changes

If you change the OCR, parsing, or clause-segmentation logic, force re-ingest the reference leases so the knowledge base is rebuilt with the cleaner clause set:

```bash
python3 run_cli.py ingest-reference --path data/reference --force
```

## Run the API

The scaffold also includes a simple FastAPI app.

### Start the API server

```bash
python3 -m lease_review_tool.cli run-api --host 127.0.0.1 --port 8000
```

### Available routes

- `GET /health`
- `POST /ingest/reference`
- `POST /analyze`

These path-based endpoints are intended for local development only.

## Suggested Local Project Layout

Reference files are not committed by default, but this structure works well locally:

```text
Lease Review Tool/
├── PRODUCT_SPEC.md
├── README.md
├── pyproject.toml
├── src/
│   └── lease_review_tool/
└── data/
    ├── reference/
    ├── parsed/
    └── runtime/
```

## Developer Notes

- The current scaffold assumes `text-embedding-3-small` sized vectors at 1536 dimensions in the database model.
- If you later change embedding dimensionality, you will need a schema migration.
- The current bootstrap command uses SQLAlchemy table creation directly. Alembic is planned but not yet wired into this first scaffold.
- The OpenAI integration path is intentionally isolated behind a single service so we can harden prompts and swap modes later without rewriting the rest of the pipeline.

## Next Recommended Steps

1. Add Alembic migrations.
2. Improve clause segmentation for lease documents.
3. Replace the heuristic field extraction with structured LLM extraction.
4. Improve benchmark generation once more reference leases are ingested.
5. Add tests around ingestion idempotency and transient analysis.
