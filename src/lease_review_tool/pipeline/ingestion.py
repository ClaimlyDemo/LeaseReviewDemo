from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..contracts import ClauseDraft
from ..document_processing import fingerprint_file, parse_document, segment_clauses
from ..llm import LLMFacade
from ..models import BenchmarkProfile, GeneratedRuleArtifact, IngestionRun, ReferenceClause, ReferenceDocument
from ..progress import NullProgressReporter
from ..schemas import IngestionItemResult, IngestionSummary
from ..utils import summarize_numeric_values


class IngestionService:
    def __init__(self, session: Session, settings: Settings, reporter=None):
        self.session = session
        self.settings = settings
        self.llm = LLMFacade(settings)
        self.reporter = reporter or NullProgressReporter()

    def ingest_path(self, path: Path, force: bool = False) -> IngestionSummary:
        started_at = datetime.utcnow()
        items: list[IngestionItemResult] = []
        target_files = self._resolve_target_files(path)
        self.reporter.message(f"Starting reference ingestion for {len(target_files)} file(s).")

        for index, target_file in enumerate(target_files, start=1):
            self.reporter.message(f"[{index}/{len(target_files)}] Ingesting {target_file.name}")
            items.append(self._ingest_single_file(target_file, force=force))

        self.reporter.message("Recomputing benchmarks and rule artifacts.")
        self._rebuild_benchmarks_and_rules()
        self.reporter.complete("Reference ingestion finished.")
        return IngestionSummary(run_started_at=started_at, items=items)

    def _ingest_single_file(self, path: Path, force: bool) -> IngestionItemResult:
        run = IngestionRun(source_path=str(path), status="processing", details_json={})
        self.session.add(run)
        self.session.flush()

        try:
            file_hash = fingerprint_file(path)
            existing = self.session.scalar(
                select(ReferenceDocument).where(ReferenceDocument.file_hash == file_hash)
            )
            if existing and not force:
                run.status = "completed"
                run.completed_at = datetime.utcnow()
                run.details_json = {"skipped": True, "reason": "existing_fingerprint"}
                return IngestionItemResult(
                    source_path=str(path),
                    document_id=existing.id,
                    status="completed",
                    clauses_created=0,
                    skipped=True,
                    detail="Skipped because this file fingerprint already exists.",
                )

            if existing and force:
                self.session.delete(existing)
                self.session.flush()

            parsed_document = parse_document(path, settings=self.settings)
            clauses = segment_clauses(parsed_document)
            ocr_pages = sum(
                1 for page in parsed_document.pages if "textract" in page.extraction_method
            )
            self.reporter.message(
                f"Parsed {parsed_document.file_type.upper()} with {len(parsed_document.pages)} page(s), "
                f"{len(clauses)} clause block(s), and Textract OCR on {ocr_pages} page(s)."
            )

            document = ReferenceDocument(
                source_path=str(path),
                source_filename=path.name,
                file_hash=file_hash,
                file_type=parsed_document.file_type,
                jurisdiction="CA",
                lease_type="residential",
                parse_status="completed",
                ingestion_status="completed",
            )
            self.session.add(document)
            self.session.flush()

            total_clauses = len(clauses)
            for clause_number, clause in enumerate(clauses, start=1):
                normalized_text = self.llm.build_normalized_summary(
                    clause.raw_text,
                    clause.clause_type,
                    clause.extracted_fields,
                )
                embedding_input = (
                    f"Clause type: {clause.clause_type}\n"
                    f"Normalized summary: {normalized_text}\n"
                    f"Clause text: {clause.raw_text}"
                )
                embedding = self.llm.embed_text(embedding_input)

                self.session.add(
                    ReferenceClause(
                        document_id=document.id,
                        clause_index=clause.clause_index,
                        clause_type=clause.clause_type,
                        page_start=clause.page_start,
                        page_end=clause.page_end,
                        source_span=clause.source_span,
                        raw_text=clause.raw_text,
                        normalized_text=normalized_text,
                        extracted_fields=clause.extracted_fields,
                        metadata_json=clause.metadata,
                        embedding_vector=embedding,
                        embedding_model=self.settings.openai_embedding_model
                        if self.llm.using_openai
                        else "mock-embedding",
                        pipeline_version="scaffold-v1",
                    )
                )
                self.reporter.progress(
                    "Embedding and storing clauses",
                    clause_number,
                    total_clauses,
                    detail=path.name,
                )

            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.details_json = {"document_id": document.id, "clauses_created": len(clauses)}
            self.reporter.message(f"Completed {path.name} with {len(clauses)} stored clause(s).")

            return IngestionItemResult(
                source_path=str(path),
                document_id=document.id,
                status="completed",
                clauses_created=len(clauses),
                skipped=False,
                detail="Reference document ingested.",
            )
        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            run.details_json = {"error": str(exc)}
            self.reporter.message(f"Failed to ingest {path.name}: {exc}")
            return IngestionItemResult(
                source_path=str(path),
                status="failed",
                clauses_created=0,
                skipped=False,
                detail=str(exc),
            )

    def _resolve_target_files(self, path: Path) -> list[Path]:
        if path.is_file():
            return [path]
        if path.is_dir():
            files = []
            for candidate in sorted(path.iterdir()):
                if candidate.suffix.lower() in {".pdf", ".docx"} and candidate.is_file():
                    files.append(candidate)
            if not files:
                raise FileNotFoundError(f"No supported PDF or DOCX files found under: {path}")
            return files
        raise FileNotFoundError(f"Path does not exist: {path}")

    def _rebuild_benchmarks_and_rules(self) -> None:
        clauses = self.session.scalars(select(ReferenceClause)).all()
        grouped: dict[str, list[ReferenceClause]] = defaultdict(list)
        for clause in clauses:
            grouped[clause.clause_type].append(clause)

        self.session.execute(delete(BenchmarkProfile))
        self.session.execute(delete(GeneratedRuleArtifact))

        total_clause_types = len(grouped)
        for clause_type_number, (clause_type, clause_group) in enumerate(grouped.items(), start=1):
            numeric_values: dict[str, list[float]] = defaultdict(list)
            for clause in clause_group:
                for key, value in (clause.extracted_fields or {}).items():
                    if isinstance(value, (int, float)):
                        numeric_values[key].append(float(value))

            field_stats: dict[str, dict[str, float]] = {}
            for field_name, values in numeric_values.items():
                if values:
                    field_stats[field_name] = summarize_numeric_values(values)

            benchmark_summary = {
                "corpus_size": len(clause_group),
                "field_stats": field_stats,
                "sample_clause_ids": [clause.id for clause in clause_group[:3]],
            }

            self.session.add(
                BenchmarkProfile(
                    clause_type=clause_type,
                    benchmark_group="ca_residential",
                    corpus_size=len(clause_group),
                    summary_json=benchmark_summary,
                )
            )

            for artifact in self.llm.generate_rule_artifacts(clause_type, benchmark_summary):
                self.session.add(
                    GeneratedRuleArtifact(
                        clause_type=artifact.clause_type,
                        short_name=artifact.short_name,
                        description=artifact.description,
                        trigger_summary=artifact.trigger_summary,
                        rationale=artifact.rationale,
                        artifact_payload=artifact.artifact_payload,
                        corpus_size=len(clause_group),
                        model_name=self.settings.openai_reasoning_model
                        if self.llm.using_openai
                        else "scaffold-local",
                    )
                )
            self.reporter.progress(
                "Benchmarking clause types",
                clause_type_number,
                total_clause_types,
                detail=clause_type,
            )
