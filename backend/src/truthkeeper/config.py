"""Process-wide configuration bootstrap.

For hackathon scope, both the FastAPI server (main.py) and the reasoning CLI
(reasoning/cli.py) load credentials and Gemini routing from validation/.env
so engineers don't need to set environment variables manually. In production
this would come from Cloud Run / Secret Manager.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_CANDIDATES = [_REPO_ROOT / "validation" / ".env", _REPO_ROOT / ".env"]


def load_runtime_env() -> None:
    """Load .env files and apply Vertex AI defaults. Idempotent."""
    for path in _ENV_CANDIDATES:
        if path.exists():
            load_dotenv(path, override=False)

    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "truthkeeper-hack-2026")
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
