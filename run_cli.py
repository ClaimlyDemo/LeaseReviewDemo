#!/usr/bin/env python3
"""Run the Lease Review Tool CLI with ``src/`` on ``sys.path``.

Use this from the repository root when ``python -m lease_review_tool.cli`` fails to
resolve the package (for example, editable installs on macOS where ``.pth`` files are
ignored). Dependencies must still be installed in your environment (``pip install .``
or ``pip install -e .``).
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
_src_str = str(_SRC)
if _src_str not in sys.path:
    sys.path.insert(0, _src_str)

from lease_review_tool.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
