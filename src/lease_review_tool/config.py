from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def _load_local_dotenv() -> None:
    dotenv_path = find_dotenv(filename=".env", usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=False)


_load_local_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Lease Review Tool"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/lease_review_tool"
    openai_api_key: str | None = None
    openai_extraction_model: str = "gpt-5.4-mini"
    openai_reasoning_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    aws_region: str | None = None
    pdf_ocr_quality_threshold: float = 0.72
    pdf_ocr_render_dpi: int = 200
    reference_document_dir: Path = Path("data/reference")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/lease_review_tool",
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_extraction_model=os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-5.4-mini"),
        openai_reasoning_model=os.getenv("OPENAI_REASONING_MODEL", "gpt-5.4"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_embedding_dimensions=int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")),
        aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        pdf_ocr_quality_threshold=float(os.getenv("PDF_OCR_QUALITY_THRESHOLD", "0.72")),
        pdf_ocr_render_dpi=int(os.getenv("PDF_OCR_RENDER_DPI", "200")),
        reference_document_dir=Path(os.getenv("REFERENCE_DOCUMENT_DIR", "data/reference")),
    )
