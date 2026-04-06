from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..document_processing import parse_document, segment_clauses
from ..llm import LLMFacade
from ..models import BenchmarkProfile, GeneratedRuleArtifact, ReferenceClause, ReferenceDocument
from ..progress import NullProgressReporter
from ..schemas import AnalysisResponse, FlagObservation
from ..utils import cosine_similarity


@dataclass(slots=True)
class _ClauseEvidence:
    score: float
    candidate_priority: float
    clause_type: str
    clause_text: str
    page: int
    source_span: str
    packet: dict[str, Any]


class AnalysisService:
    def __init__(self, session: Session, settings: Settings, reporter=None):
        self.session = session
        self.settings = settings
        self.llm = LLMFacade(settings)
        self.reporter = reporter or NullProgressReporter()

    def analyze_path(self, path: Path) -> AnalysisResponse:
        self.reporter.message(f"Starting analysis for {path.name}.")
        parsed_document = parse_document(path, settings=self.settings)
        clause_drafts = segment_clauses(parsed_document)
        ocr_pages = sum(1 for page in parsed_document.pages if "textract" in page.extraction_method)
        self.reporter.message(
            f"Parsed {parsed_document.file_type.upper()} with {len(parsed_document.pages)} page(s), "
            f"{len(clause_drafts)} clause block(s), and Textract OCR on {ocr_pages} page(s)."
        )

        reference_clauses = self.session.scalars(select(ReferenceClause)).all()
        if not reference_clauses:
            raise RuntimeError(
                "The knowledge base is empty. Run the reference ingestion stage before analyzing a lease."
            )
        self.reporter.message(f"Loaded knowledge base with {len(reference_clauses)} reference clause(s).")

        benchmarks = {
            profile.clause_type: profile
            for profile in self.session.scalars(select(BenchmarkProfile)).all()
        }
        rules_by_type: dict[str, list[GeneratedRuleArtifact]] = defaultdict(list)
        for artifact in self.session.scalars(select(GeneratedRuleArtifact)).all():
            rules_by_type[artifact.clause_type].append(artifact)

        self.reporter.message("Creating batched embeddings for candidate clause blocks.")
        embedding_inputs = [
            f"Clause type: {clause.clause_type}\nNormalized summary: {clause.normalized_text}\nClause text: {clause.raw_text}"
            for clause in clause_drafts
        ]
        clause_embeddings = self.llm.embed_many_texts(embedding_inputs)

        evidence_rows: list[_ClauseEvidence] = []
        total_clauses = len(clause_drafts)
        for clause_number, (clause, embedding) in enumerate(zip(clause_drafts, clause_embeddings), start=1):
            evidence_rows.append(
                self._build_clause_evidence(
                    clause=clause,
                    embedding=embedding,
                    reference_clauses=reference_clauses,
                    benchmark_profile=benchmarks.get(clause.clause_type),
                    rule_artifacts=rules_by_type.get(clause.clause_type, []),
                )
            )
            self.reporter.progress(
                "Analyzing clause blocks",
                clause_number,
                total_clauses,
                detail=path.name,
            )

        document_count = self.session.scalar(select(func.count()).select_from(ReferenceDocument)) or 0
        clause_count = len(reference_clauses)
        kb_snapshot = f"documents:{document_count};clauses:{clause_count}"

        candidate_packets = self._select_llm_candidates(evidence_rows)
        self.reporter.message(
            f"Prepared {len(candidate_packets)} candidate evidence packet(s) for final gpt-5.4 flagging."
        )

        llm_flags = self.llm.generate_final_flags(
            candidate_packets=candidate_packets,
            kb_snapshot=kb_snapshot,
            max_flags=10,
        )
        flags = self._coerce_llm_flags(llm_flags, evidence_rows)

        response = AnalysisResponse(
            analysis_timestamp=datetime.utcnow(),
            analysis_mode="prototype_structured_observations_gpt_5_4",
            kb_snapshot=kb_snapshot,
            limitations_note="Prototype built on a small California residential reference set.",
            flags=flags,
        )
        self.reporter.complete(f"Analysis finished with {len(response.flags)} flagged observation(s).")
        return response

    def _build_clause_evidence(
        self,
        clause,
        embedding: list[float],
        reference_clauses: list[ReferenceClause],
        benchmark_profile: BenchmarkProfile | None,
        rule_artifacts: list[GeneratedRuleArtifact],
    ) -> _ClauseEvidence:
        normalized_text = clause.normalized_text

        comparable_references = [
            ref for ref in reference_clauses if ref.clause_type == clause.clause_type
        ]
        if not comparable_references:
            comparable_references = reference_clauses

        similarities: list[tuple[ReferenceClause, float]] = []
        for ref in comparable_references:
            similarities.append((ref, cosine_similarity(embedding, ref.embedding_vector)))
        similarities.sort(key=lambda item: item[1], reverse=True)

        reasoning_type: list[str] = []
        comparison_notes: list[str] = []
        rule_artifact_ids: list[str] = []
        matched_reference_clauses = [ref.id for ref, _ in similarities[:3]]
        score = 0.0

        top_similarity = similarities[0][1] if similarities else 0.0
        if similarities and top_similarity < 0.72:
            reasoning_type.append("semantic_anomaly")
            comparison_notes.append(
                f"Closest reference similarity for this clause type is {top_similarity:.2f}, which is low for the current reference set."
            )
            score += 0.35

        benchmark_summary = benchmark_profile.summary_json if benchmark_profile else {}
        field_stats = benchmark_summary.get("field_stats", {}) if benchmark_summary else {}
        for field_name, value in clause.extracted_fields.items():
            stats = field_stats.get(field_name)
            if not stats or not isinstance(value, (int, float)):
                continue
            minimum = stats.get("min")
            maximum = stats.get("max")
            if minimum is None or maximum is None:
                continue
            if float(value) < float(minimum) or float(value) > float(maximum):
                if "parameter_anomaly" not in reasoning_type:
                    reasoning_type.append("parameter_anomaly")
                comparison_notes.append(
                    f"{field_name}={value} falls outside the current reference range [{minimum}, {maximum}]."
                )
                score += 0.4

        for artifact in rule_artifacts:
            payload = artifact.artifact_payload or {}
            kind = payload.get("kind")
            if kind == "semantic_distance" and similarities and top_similarity < float(
                payload.get("min_similarity", 0.72)
            ):
                if "rule_red_flag" not in reasoning_type:
                    reasoning_type.append("rule_red_flag")
                rule_artifact_ids.append(artifact.id)
                comparison_notes.append(artifact.description)
                score += 0.15
            if kind == "numeric_range":
                field_name = payload.get("field_name")
                if not isinstance(field_name, str):
                    continue
                if field_name not in clause.extracted_fields:
                    continue
                current_value = clause.extracted_fields[field_name]
                if not isinstance(current_value, (int, float)):
                    continue
                minimum = payload.get("min")
                maximum = payload.get("max")
                if minimum is None or maximum is None:
                    continue
                if float(current_value) < float(minimum) or float(current_value) > float(maximum):
                    if "rule_red_flag" not in reasoning_type:
                        reasoning_type.append("rule_red_flag")
                    rule_artifact_ids.append(artifact.id)
                    comparison_notes.append(artifact.description)
                    score += 0.15

        reference_matches = []
        for ref, similarity in similarities[:2]:
            reference_matches.append(
                {
                    "reference_clause_id": ref.id,
                    "clause_type": ref.clause_type,
                    "similarity": round(similarity, 3),
                    "normalized_text": self._truncate_text(ref.normalized_text, 260),
                    "raw_text_excerpt": self._truncate_text(ref.raw_text, 280),
                }
            )

        candidate_priority = score
        if clause.clause_type != "other":
            candidate_priority += 0.10
        if clause.extracted_fields:
            candidate_priority += 0.05
        if top_similarity < 0.85:
            candidate_priority += 0.05

        packet = {
            "source_span": clause.source_span,
            "page": clause.page_start,
            "clause_type": clause.clause_type,
            "clause_text": self._truncate_text(clause.raw_text, 900),
            "normalized_summary": self._truncate_text(normalized_text, 260),
            "extracted_fields": clause.extracted_fields,
            "local_signals": {
                "heuristic_score": round(score, 3),
                "top_similarity": round(top_similarity, 3),
                "reasoning_type": reasoning_type,
                "comparison_notes": comparison_notes,
            },
            "reference_matches": reference_matches,
            "benchmark_summary": benchmark_summary,
            "rule_artifacts": [
                {
                    "id": artifact.id,
                    "short_name": artifact.short_name,
                    "description": artifact.description,
                    "trigger_summary": artifact.trigger_summary,
                }
                for artifact in rule_artifacts[:3]
            ],
        }

        return _ClauseEvidence(
            score=score,
            candidate_priority=candidate_priority,
            clause_type=clause.clause_type,
            clause_text=clause.raw_text,
            page=clause.page_start,
            source_span=clause.source_span,
            packet=packet,
        )

    def _select_llm_candidates(self, evidence_rows: list[_ClauseEvidence]) -> list[dict[str, Any]]:
        ranked = sorted(
            evidence_rows,
            key=lambda row: (row.candidate_priority, row.page, row.source_span),
            reverse=True,
        )

        selected = ranked[:25]
        if not selected:
            return []

        return [row.packet for row in selected]

    def _coerce_llm_flags(
        self,
        llm_flags: list[dict[str, Any]],
        evidence_rows: list[_ClauseEvidence],
    ) -> list[FlagObservation]:
        evidence_lookup = {row.source_span: row for row in evidence_rows}
        deduped: list[FlagObservation] = []
        seen: set[str] = set()

        for raw_flag in llm_flags:
            source_span = raw_flag.get("source_span")
            if not isinstance(source_span, str):
                continue
            if source_span in seen:
                continue
            evidence = evidence_lookup.get(source_span)
            if evidence is None:
                continue

            confidence = raw_flag.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)):
                confidence = 0.5
            confidence = max(0.0, min(1.0, float(confidence)))

            flag_payload = {
                "title": raw_flag.get("title") or self._build_title(evidence.clause_type),
                "observation": raw_flag.get("observation")
                or f"This {evidence.clause_type.replace('_', ' ')} clause stands out against the current reference set.",
                "why_flagged": raw_flag.get("why_flagged") or "Flagged by gpt-5.4 using retrieved reference evidence.",
                "flag_type": raw_flag.get("flag_type") or evidence.clause_type,
                "confidence": round(confidence, 2),
                "clause_text": evidence.clause_text,
                "page": evidence.page,
                "source_span": evidence.source_span,
                "reasoning_type": raw_flag.get("reasoning_type") or [],
                "matched_reference_clauses": raw_flag.get("matched_reference_clauses") or [],
                "comparison_notes": raw_flag.get("comparison_notes") or [],
                "rule_artifact_ids": raw_flag.get("rule_artifact_ids") or [],
            }
            deduped.append(FlagObservation.model_validate(flag_payload))
            seen.add(source_span)

        deduped.sort(key=lambda flag: ((flag.page or 0), flag.source_span))
        return deduped[:10]

    def _build_title(self, clause_type: str) -> str:
        label = clause_type.replace("_", " ").strip() or "clause"
        return f"Potentially unusual {label} clause"

    def _truncate_text(self, text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: limit - 3]}..."
