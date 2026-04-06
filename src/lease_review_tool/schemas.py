from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestReferenceRequest(BaseModel):
    path: str
    force: bool = False


class AnalyzeLeaseRequest(BaseModel):
    path: str


class IngestionItemResult(BaseModel):
    source_path: str
    document_id: str | None = None
    status: str
    clauses_created: int = 0
    skipped: bool = False
    detail: str | None = None


class IngestionSummary(BaseModel):
    run_started_at: datetime
    items: list[IngestionItemResult]


class FlagObservation(BaseModel):
    title: str
    observation: str
    why_flagged: str
    flag_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    clause_text: str
    page: int | None = None
    source_span: str
    reasoning_type: list[str] = Field(default_factory=list)
    matched_reference_clauses: list[str] = Field(default_factory=list)
    comparison_notes: list[str] = Field(default_factory=list)
    rule_artifact_ids: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    analysis_timestamp: datetime
    analysis_mode: str
    kb_snapshot: str
    limitations_note: str
    flags: list[FlagObservation]

