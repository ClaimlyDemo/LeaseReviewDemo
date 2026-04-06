from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ParsedPage:
    page_number: int
    text: str
    extraction_method: str = "unknown"
    quality_score: float | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    source_path: Path
    file_type: str
    pages: list[ParsedPage]

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


@dataclass(slots=True)
class ClauseDraft:
    clause_index: int
    raw_text: str
    clause_type: str
    page_start: int
    page_end: int
    source_span: str
    extracted_fields: dict[str, float | int | str | bool]
    normalized_text: str
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass(slots=True)
class RuleArtifactDraft:
    clause_type: str
    short_name: str
    description: str
    trigger_summary: str
    rationale: str
    artifact_payload: dict[str, object]
