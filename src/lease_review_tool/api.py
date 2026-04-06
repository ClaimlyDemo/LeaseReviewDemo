from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .config import get_settings
from .db import session_scope
from .pipeline.analysis import AnalysisService
from .pipeline.ingestion import IngestionService
from .preflight import assert_pipeline_ready
from .progress import ConsoleProgressReporter
from .schemas import AnalyzeLeaseRequest, AnalysisResponse, IngestReferenceRequest, IngestionSummary

app = FastAPI(title="Lease Review Tool")


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


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: AnalyzeLeaseRequest) -> AnalysisResponse:
    settings = get_settings()
    try:
        assert_pipeline_ready(settings)
        reporter = ConsoleProgressReporter(prefix="api-analyze")
        with session_scope() as session:
            service = AnalysisService(session=session, settings=settings, reporter=reporter)
            return service.analyze_path(Path(payload.path))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
