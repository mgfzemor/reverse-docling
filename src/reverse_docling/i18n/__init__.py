"""Per-language label tables. Missing keys fall back to English (and are reported)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)
I18N_DIR = Path(__file__).parent


@lru_cache
def load_table(code: str) -> dict[str, Any]:
    path = I18N_DIR / f"{code}.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _lookup(table: dict[str, Any], key: str) -> Any:
    node: Any = table
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def flatten_keys(table: dict[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for k, v in table.items():
        full = f"{prefix}{k}"
        if isinstance(v, dict):
            keys |= flatten_keys(v, full + ".")
        else:
            keys.add(full)
    return keys


class Translator:
    def __init__(self, code: str):
        self.code = code
        self.table = load_table(code)
        self.fallback = load_table("en")

    def get(self, key: str) -> Any:
        value = _lookup(self.table, key)
        if value is None:
            value = _lookup(self.fallback, key)
            if value is None:
                raise KeyError(f"i18n key '{key}' missing in '{self.code}' and 'en'")
            log.warning("i18n key '%s' missing for '%s', using English", key, self.code)
        return value

    def __call__(self, key: str, **params: Any) -> str:
        value = self.get(key)
        return str(value).format(**params) if params else str(value)

    def list(self, key: str) -> list[Any]:
        value = self.get(key)
        if not isinstance(value, list):
            raise TypeError(f"i18n key '{key}' is not a list")
        return value
