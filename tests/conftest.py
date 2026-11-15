"""Shared fixtures. Tests that need the OOM symbol sets are skipped if OOM is not installed."""

from pathlib import Path

import pytest

from olprep.ressourcen import OOM_SYMBOL_SETS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

needs_oom = pytest.mark.skipif(not OOM_SYMBOL_SETS.exists(),
                               reason=f"OOM-Symbolsätze nicht gefunden: {OOM_SYMBOL_SETS}")
