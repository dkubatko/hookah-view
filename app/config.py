"""Runtime settings, all overridable through environment variables."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from ./.env without overriding the real environment."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
STATIC_DIR = ROOT / "static"

PORT = _int("PORT", 8440)

# Stock and prices move often and the WHM fetch is cheap (~35 requests).
WHM_REFRESH_MINUTES = _int("WHM_REFRESH_MINUTES", 120)
# Ratings move slowly; the HTR crawl is ~120 requests.
HTR_REFRESH_HOURS = _int("HTR_REFRESH_HOURS", 24)

# Optional shared secret for write endpoints (refresh, match fixes).
# Unset means anyone who can reach the app may use them.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

MODERNMT_API_KEY = os.environ.get("MODERNMT_API_KEY", "")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
COMMIT = os.environ.get("GIT_COMMIT", "dev")
