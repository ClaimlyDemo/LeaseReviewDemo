from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class NullProgressReporter:
    def message(self, _message: str) -> None:
        return

    def progress(self, _label: str, _current: int, _total: int, detail: str | None = None) -> None:
        return

    def complete(self, _message: str) -> None:
        return


@dataclass
class ConsoleProgressReporter:
    prefix: str = "pipeline"
    stream: TextIO = field(default_factory=lambda: sys.stderr)
    min_render_interval_seconds: float = 0.1

    def __post_init__(self) -> None:
        self._last_render_at: float = 0.0
        self._last_non_tty_bucket: tuple[str, int] | None = None
        self._line_active = False

    def message(self, message: str) -> None:
        self._finish_inline_line()
        print(f"[{self.prefix}] {message}", file=self.stream, flush=True)

    def progress(self, label: str, current: int, total: int, detail: str | None = None) -> None:
        if total <= 0:
            return

        current = max(0, min(current, total))
        ratio = current / total
        percent = int(ratio * 100)
        detail_suffix = f" | {detail}" if detail else ""

        if self.stream.isatty():
            now = time.monotonic()
            if current < total and (now - self._last_render_at) < self.min_render_interval_seconds:
                return
            self._last_render_at = now
            width = 24
            filled = int(width * ratio)
            bar = "#" * filled + "-" * (width - filled)
            line = f"[{self.prefix}] {label:<24} [{bar}] {current}/{total} ({percent:>3} %){detail_suffix}"
            print(f"\r{line}", end="", file=self.stream, flush=True)
            self._line_active = True
            if current == total:
                self._finish_inline_line()
            return

        bucket = percent // 10
        bucket_key = (label, bucket)
        should_print = current in {1, total} or self._last_non_tty_bucket != bucket_key
        if should_print:
            self._last_non_tty_bucket = bucket_key
            print(
                f"[{self.prefix}] {label}: {current}/{total} ({percent} %){detail_suffix}",
                file=self.stream,
                flush=True,
            )

    def complete(self, message: str) -> None:
        self._finish_inline_line()
        print(f"[{self.prefix}] {message}", file=self.stream, flush=True)

    def _finish_inline_line(self) -> None:
        if self._line_active:
            print(file=self.stream, flush=True)
            self._line_active = False

