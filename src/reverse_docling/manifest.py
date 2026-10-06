"""JSONL manifest: one labelled record per generated document."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import ManifestRecord


def to_jsonable(value: Any) -> Any:
    """Drop render-only keys (prefixed with '_') and convert dates/decimals."""
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class ManifestWriter:
    def __init__(self, path: Path, append: bool = False):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a" if append else "w", encoding="utf-8")

    def write(self, record: ManifestRecord) -> None:
        self._fh.write(record.model_dump_json() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "ManifestWriter":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
