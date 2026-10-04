"""Tiny JSON-file persistence with atomic writes.

The whole dataset is a few MB, so plain JSON files in DATA_DIR are simpler
and faster than a database: everything is loaded into memory at startup and
written back after each refresh.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app import config


def path(name: str) -> Path:
    return config.DATA_DIR / name


def load(name: str, default: Any = None) -> Any:
    try:
        return json.loads(path(name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except ValueError:
        # A corrupt file should not take the app down; start from scratch.
        return default


def save(name: str, data: Any) -> None:
    target = path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
