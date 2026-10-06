"""Discover doc types and their templates."""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

from ..render import TEMPLATES_DIR
from .base import DocType


@lru_cache
def doc_types() -> dict[str, DocType]:
    """Every module in this package that defines a DocType subclass instance named `DOC_TYPE`."""
    from .. import doctypes as pkg

    found: dict[str, DocType] = {}
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name in {"base", "registry"}:
            continue
        module = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        doc_type = getattr(module, "DOC_TYPE", None)
        if isinstance(doc_type, DocType):
            found[doc_type.name] = doc_type
    return dict(sorted(found.items()))


def templates_for(doc_type: str) -> list[str]:
    """Template ids (file stems without .html.j2) for a doc type, sorted."""
    folder = TEMPLATES_DIR / doc_type
    return sorted(p.name.removesuffix(".html.j2") for p in folder.glob("*.html.j2"))


def get_doc_type(name: str) -> DocType:
    types = doc_types()
    if name not in types:
        raise ValueError(f"Unknown document type '{name}'. Available: {', '.join(types)}")
    return types[name]
