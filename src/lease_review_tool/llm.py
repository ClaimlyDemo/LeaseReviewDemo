from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings
from .contracts import RuleArtifactDraft


class LLMFacade:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = self._build_client()

    @property
    def using_openai(self) -> bool:
        return self._client is not None

    def embed_text(self, text: str) -> list[float]:
        return self.embed_many_texts([text])[0]

    def embed_many_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            raise RuntimeError(
                "OpenAI client is unavailable. Refusing to generate embeddings without a configured API key."
            )
        if not texts:
            return []

        kwargs = {
            "model": self.settings.openai_embedding_model,
            "input": texts,
            "encoding_format": "float",
        }
        if self.settings.openai_embedding_model.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.settings.openai_embedding_dimensions

        try:
            response = self._client.embeddings.create(**kwargs)
            return [list(item.embedding) for item in response.data]
        except Exception as exc:
            raise RuntimeError(
                "OpenAI embeddings request failed during pipeline execution."
            ) from exc

    def build_normalized_summary(
        self,
        raw_text: str,
        clause_type: str,
        extracted_fields: dict[str, object],
    ) -> str:
        if not self._client:
            raise RuntimeError(
                "OpenAI client is unavailable. Refusing to generate normalized summaries without a configured API key."
            )

        schema = {
            "type": "json_schema",
            "name": "clause_summary",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                },
                "required": ["summary"],
                "additionalProperties": False,
            },
        }
        prompt = (
            "Summarize the lease clause in one concise sentence for internal knowledge-base storage. "
            "Preserve legal substance, mention extracted values when relevant, and do not give advice.\n\n"
            f"Clause type: {clause_type}\n"
            f"Extracted fields: {json.dumps(extracted_fields, sort_keys=True)}\n"
            f"Clause text: {raw_text}"
        )
        try:
            response = self._client.responses.create(
                model=self.settings.openai_extraction_model,
                instructions="You are generating compact internal summaries for a lease knowledge base.",
                input=prompt,
                reasoning={"effort": "low"},
                text={"format": schema},
            )
            payload = json.loads(response.output_text)
            return payload["summary"].strip()
        except Exception as exc:
            raise RuntimeError(
                "OpenAI structured summary request failed during pipeline execution."
            ) from exc

    def generate_rule_artifacts(
        self,
        clause_type: str,
        benchmark_summary: dict[str, object],
    ) -> list[RuleArtifactDraft]:
        drafts: list[RuleArtifactDraft] = []
        field_stats = benchmark_summary.get("field_stats", {})
        corpus_size = int(benchmark_summary.get("corpus_size", 0))

        drafts.append(
            RuleArtifactDraft(
                clause_type=clause_type,
                short_name=f"{clause_type} semantic distance check",
                description=(
                    f"Flag {clause_type} clauses that are semantically distant from the current "
                    "California residential reference set."
                ),
                trigger_summary="Trigger when the clause meaning appears materially different from the closest reference clauses.",
                rationale=(
                    f"The current corpus for {clause_type} has {corpus_size} reference clauses. "
                    "Large semantic distance may indicate unusual drafting."
                ),
                artifact_payload={"kind": "semantic_distance", "min_similarity": 0.72},
            )
        )

        for field_name, stats in field_stats.items():
            minimum = stats.get("min")
            maximum = stats.get("max")
            if minimum is None or maximum is None:
                continue

            drafts.append(
                RuleArtifactDraft(
                    clause_type=clause_type,
                    short_name=f"{clause_type} {field_name} range check",
                    description=(
                        f"Flag {clause_type} clauses when {field_name} falls outside the current reference range."
                    ),
                    trigger_summary=(
                        f"Trigger when {field_name} is below {minimum} or above {maximum} "
                        "for the current reference set."
                    ),
                    rationale=(
                        "This range is derived from the currently ingested reference leases and should be "
                        "treated as a small-corpus heuristic."
                    ),
                    artifact_payload={
                        "kind": "numeric_range",
                        "field_name": field_name,
                        "min": minimum,
                        "max": maximum,
                    },
                )
            )

        return drafts

    def generate_final_flags(
        self,
        candidate_packets: list[dict[str, Any]],
        kb_snapshot: str,
        max_flags: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._client:
            raise RuntimeError(
                "OpenAI client is unavailable. Refusing to run final flagging without a configured API key."
            )

        schema = {
            "type": "json_schema",
            "name": "lease_final_flags",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "flags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "observation": {"type": "string"},
                                "why_flagged": {"type": "string"},
                                "flag_type": {"type": "string"},
                                "confidence": {"type": "number"},
                                "clause_text": {"type": "string"},
                                "page": {"type": "integer"},
                                "source_span": {"type": "string"},
                                "reasoning_type": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "matched_reference_clauses": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "comparison_notes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "rule_artifact_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "title",
                                "observation",
                                "why_flagged",
                                "flag_type",
                                "confidence",
                                "clause_text",
                                "page",
                                "source_span",
                                "reasoning_type",
                                "matched_reference_clauses",
                                "comparison_notes",
                                "rule_artifact_ids",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["flags"],
                "additionalProperties": False,
            },
        }

        prompt = (
            "Review the candidate clause-evidence packets and decide which clauses should become final flagged observations. "
            f"Return at most {max_flags} flags.\n\n"
            "Operating rules:\n"
            "- This is for a California residential lease-review prototype.\n"
            "- The end user is not chatting with you directly.\n"
            "- Return observations only. Do not make recommendations or tell the user what to do.\n"
            "- Use only the evidence provided in the packets.\n"
            "- Prefer clauses that are materially unusual, sharp, risky, or important to surface.\n"
            "- If evidence is weak, do not flag the clause.\n"
            "- Keep `reasoning_type` grounded in the packet evidence, such as `semantic_anomaly`, `parameter_anomaly`, or `rule_red_flag`.\n"
            "- Preserve source span, page, and clause text from the packet.\n\n"
            f"Knowledge-base snapshot: {kb_snapshot}\n\n"
            f"Candidate packets:\n{json.dumps(candidate_packets, indent=2, ensure_ascii=True)}"
        )

        try:
            response = self._client.responses.create(
                model=self.settings.openai_reasoning_model,
                instructions=(
                    "You are an internal legal lease-analysis engine. "
                    "Choose the strongest clause-level observations and return strict structured JSON only."
                ),
                input=prompt,
                reasoning={"effort": "medium"},
                text={"format": schema},
            )
            payload = json.loads(response.output_text)
            flags = payload.get("flags", [])
            if not isinstance(flags, list):
                raise RuntimeError("Structured final-flagging response did not contain a valid flags array.")
            return flags[:max_flags]
        except Exception as exc:
            raise RuntimeError("OpenAI final flagging request failed during lease analysis.") from exc

    def _build_client(self):
        if not self.settings.openai_api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        return OpenAI(api_key=self.settings.openai_api_key)
