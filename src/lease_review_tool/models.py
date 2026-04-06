from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


EMBEDDING_DIMENSIONS = 1536


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class ReferenceDocument(Base):
    __tablename__ = "reference_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(32), default="CA")
    lease_type: Mapped[str] = mapped_column(String(32), default="residential")
    parse_status: Mapped[str] = mapped_column(String(32), default="completed")
    ingestion_status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    clauses: Mapped[list["ReferenceClause"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class ReferenceClause(Base):
    __tablename__ = "reference_clauses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("reference_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clause_index: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_span: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_fields: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    embedding_vector: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String(64), default="scaffold-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    document: Mapped["ReferenceDocument"] = relationship(back_populates="clauses")


class BenchmarkProfile(Base):
    __tablename__ = "benchmark_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clause_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    benchmark_group: Mapped[str] = mapped_column(String(64), nullable=False, default="ca_residential")
    corpus_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class GeneratedRuleArtifact(Base):
    __tablename__ = "generated_rule_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    clause_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    short_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    corpus_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_name: Mapped[str] = mapped_column(String(128), default="scaffold-local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

