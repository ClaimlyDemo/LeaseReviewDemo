from __future__ import annotations

import os

from .config import Settings
from .db import assert_database_connection


def assert_openai_ready(settings: Settings) -> None:
    if not settings.openai_api_key or not settings.openai_api_key.strip():
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Refusing to run the ingestion or analysis pipeline without a configured API key."
        )

    try:
        import openai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python SDK is not installed. Install project dependencies before running the ingestion or analysis pipeline."
        ) from exc


def assert_pipeline_ready(settings: Settings) -> None:
    assert_openai_ready(settings)
    assert_aws_ready(settings)
    assert_database_connection(settings)


def assert_aws_ready(settings: Settings) -> None:
    try:
        import boto3  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is not installed. Install project dependencies before running the ingestion or analysis pipeline."
        ) from exc

    if not settings.aws_region or not settings.aws_region.strip():
        raise RuntimeError(
            "AWS_REGION is missing. Configure AWS_REGION in .env before running PDF analysis with Textract OCR fallback."
        )

    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if bool(access_key) != bool(secret_key):
        raise RuntimeError(
            "AWS credentials are incomplete. Set both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither if you are using another boto3 credential source."
        )
