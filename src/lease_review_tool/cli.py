from __future__ import annotations

import argparse
from pathlib import Path

from .config import get_settings
from .db import init_db, session_scope
from .pipeline.analysis import AnalysisService
from .pipeline.ingestion import IngestionService
from .preflight import assert_pipeline_ready
from .progress import ConsoleProgressReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lease Review Tool backend CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create database tables and the vector extension.")

    ingest_parser = subparsers.add_parser("ingest-reference", help="Ingest reference lease files.")
    ingest_parser.add_argument("--path", required=True, help="Path to a file or directory.")
    ingest_parser.add_argument("--force", action="store_true", help="Reprocess existing files.")

    analyze_parser = subparsers.add_parser("analyze-lease", help="Analyze a transient lease file.")
    analyze_parser.add_argument("--path", required=True, help="Path to the lease file.")
    analyze_parser.add_argument("--output", help="Optional JSON output file.")

    api_parser = subparsers.add_parser("run-api", help="Run the FastAPI development server.")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()

    try:
        if args.command == "init-db":
            init_db(settings)
            print("Database initialized.")
            return

        if args.command == "ingest-reference":
            assert_pipeline_ready(settings)
            reporter = ConsoleProgressReporter(prefix="ingest")
            with session_scope() as session:
                service = IngestionService(session=session, settings=settings, reporter=reporter)
                result = service.ingest_path(Path(args.path), force=args.force)
                print(result.model_dump_json(indent=2))
            return

        if args.command == "analyze-lease":
            assert_pipeline_ready(settings)
            reporter = ConsoleProgressReporter(prefix="analyze")
            with session_scope() as session:
                service = AnalysisService(session=session, settings=settings, reporter=reporter)
                result = service.analyze_path(Path(args.path))
                payload = result.model_dump_json(indent=2)
                if args.output:
                    out_path = Path(args.output).expanduser()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(payload, encoding="utf-8")
                    print(f"Wrote analysis to {out_path.resolve()}", flush=True)
                else:
                    print(payload)
            return

        if args.command == "run-api":
            import uvicorn
            from .api import app

            uvicorn.run(app, host=args.host, port=args.port)
            return
    except Exception as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")
