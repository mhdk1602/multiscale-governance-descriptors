"""Make the src/ package importable without an editable install.

Lets `pytest` run from a clean checkout (and in CI) regardless of whether
`governance_descriptors` has been pip-installed.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
