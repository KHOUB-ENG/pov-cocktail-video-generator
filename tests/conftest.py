"""Shared pytest setup: put `src/` and the orchestrator on the import path,
and provide a dummy API key so importing config-dependent modules never
requires a real Google key in CI."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The orchestrator imports the `database` package by adding `src/` to the path
# at runtime; mirror that here so `import main` works from the tests.
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "orchestrator"))
sys.path.insert(0, str(ROOT / "src" / "config"))

# Never needs to be valid — only presence is checked by geminiAPIsettings.
os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-real")
