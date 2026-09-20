"""Global pytest configuration ensuring src/ is always resolvable."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path regardless of execution directory
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
