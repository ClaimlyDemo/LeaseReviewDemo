from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import session_scope
from .pipeline.analysis import AnalysisService
from .pipeline.ingestion import IngestionService
from .preflight import assert_pipeline_ready
from .progress import ConsoleProgressReporter
from .schemas import AnalyzeLeaseRequest, AnalysisResponse, IngestReferenceRequest, IngestionSummary

app = FastAPI(title="Lease Review Tool")

# Keep browser uploads simple for the hosted demo by allowing cross-origin
# requests to the public analysis endpoint.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_UPLOAD_SUFFIXES = {".pdf", ".docx"}
DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/reference", response_model=IngestionSummary)
def ingest_reference(payload: IngestReferenceRequest) -> IngestionSummary:
    settings = get_settings()
    try:
        assert_pipeline_ready(settings)
        reporter = ConsoleProgressReporter(prefix="api-ingest")
        with session_scope() as session:
            service = IngestionService(session=session, settings=settings, reporter=reporter)
            return service.ingest_path(Path(payload.path), force=payload.force)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _run_analysis_for_path(path: Path, reporter_prefix: str = "api-analyze") -> AnalysisResponse:
    settings = get_settings()
    assert_pipeline_ready(settings)
    reporter = ConsoleProgressReporter(prefix=reporter_prefix)
    with session_scope() as session:
        service = AnalysisService(session=session, settings=settings, reporter=reporter)
        return service.analyze_path(path)


def _normalize_upload_filename(filename: str, content_type: str | None) -> str:
    candidate = Path(filename).name.strip()
    suffix = Path(candidate).suffix.lower()
    if suffix in SUPPORTED_UPLOAD_SUFFIXES:
        return candidate

    normalized_content_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type == "application/pdf":
        inferred_suffix = ".pdf"
    elif normalized_content_type in DOCX_CONTENT_TYPES:
        inferred_suffix = ".docx"
    else:
        raise HTTPException(status_code=400, detail="Upload must be a PDF or DOCX file.")

    stem = Path(candidate).stem.strip() if candidate else "lease-upload"
    return f"{stem or 'lease-upload'}{inferred_suffix}"


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: AnalyzeLeaseRequest) -> AnalysisResponse:
    try:
        return _run_analysis_for_path(Path(payload.path))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/analyze/upload", response_model=AnalysisResponse)
async def analyze_upload(
    request: Request,
    filename: str = Query(..., min_length=1, description="Original uploaded filename."),
) -> AnalysisResponse:
    safe_filename = _normalize_upload_filename(
        filename=filename,
        content_type=request.headers.get("content-type"),
    )
    file_bytes = await request.body()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="lease-upload-",
            suffix=Path(safe_filename).suffix.lower(),
            delete=False,
        ) as handle:
            handle.write(file_bytes)
            temp_path = Path(handle.name)

        return _run_analysis_for_path(temp_path, reporter_prefix="api-upload")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
