"""Doc-type interface and helpers shared by all doc types.

All institutions (banks, airlines, hotels, utilities, registries) are fictional: names are built from
per-language word lists and logos are generated SVG monograms, so no real brand is imitated.
"""

from __future__ import annotations

import datetime as dt
import random
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from ..i18n import Translator
from ..locales import Language
from ..models import Identity

PALETTES = [
    ("#0b3d91", "#e8eef9"), ("#00684a", "#e6f4ee"), ("#8a1538", "#f8e9ee"), ("#1f2937", "#eef0f3"),
    ("#b45309", "#fdf3e7"), ("#4c1d95", "#f1ecfb"), ("#0e7490", "#e6f6f9"), ("#7f1d1d", "#f9ecec"),
]


@dataclass
class Brand:
    name: str
    primary: str
    light: str
    logo: Markup  # inline SVG

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name}


def logo_svg(name: str, color: str, rng: random.Random, size: int = 48) -> Markup:
    letters = "".join(w[0] for w in name.replace("-", " ").split() if w and w[0].isalpha())[:2].upper()
    if not letters.isascii():  # e.g. Arabic/CJK names: use one native glyph
        letters = name.strip()[0]
    shape = rng.choice(["circle", "rounded", "diamond", "shield"])
    c = size / 2
    shapes = {
        "circle": f'<circle cx="{c}" cy="{c}" r="{c - 2}" fill="{color}"/>',
        "rounded": f'<rect x="2" y="2" width="{size - 4}" height="{size - 4}" rx="10" fill="{color}"/>',
        "diamond": f'<polygon points="{c},2 {size - 2},{c} {c},{size - 2} 2,{c}" fill="{color}"/>',
        "shield": f'<path d="M{c} 2 L{size - 4} 9 V{c} Q{size - 4} {size - 6} {c} {size - 2} '
                  f'Q4 {size - 6} 4 {c} V9 Z" fill="{color}"/>',
    }
    accent = (f'<circle cx="{size - 9}" cy="9" r="5" fill="#fff" opacity=".35"/>'
              if rng.random() < 0.5 else "")
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'{shapes[shape]}{accent}<text x="{c}" y="{c}" dy=".35em" text-anchor="middle" fill="#fff" '
        f'font-family="sans-serif" font-weight="700" font-size="{size * 0.38:.0f}">{letters}</text></svg>'
    )


def make_brand(t: Translator, kind: str, rng: random.Random) -> Brand:
    """kind is a key under `brands` in the i18n tables, e.g. 'bank', 'airline', 'hotel'."""
    pattern = rng.choice(t.list(f"brands.{kind}"))
    word = rng.choice(t.list("brands.words"))
    name = pattern.format(word=word)
    primary, light = rng.choice(PALETTES)
    return Brand(name=name, primary=primary, light=light, logo=logo_svg(name, primary, rng))


def ref_code(rng: random.Random, length: int = 6, alphabet: str = string.ascii_uppercase + string.digits) -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


def random_date(rng: random.Random, start: dt.date, end: dt.date) -> dt.date:
    return start + dt.timedelta(days=rng.randint(0, max(0, (end - start).days)))


def today_like(rng: random.Random) -> dt.date:
    """An 'issue date' within the last ~2 years, fixed relative to a constant anchor for reproducibility."""
    anchor = dt.date(2026, 9, 30)
    return anchor - dt.timedelta(days=rng.randint(0, 730))


def money(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high), 2)


@dataclass
class BuildContext:
    identity: Identity
    lang: Language
    t: Translator
    rng: random.Random


class DocType(ABC):
    """A document class. `build` returns the variable data passed to templates as `doc`.

    Values in `doc` should be JSON-friendly (dates are fine) because they are recorded as
    ground-truth fields in the manifest; put render-only objects (logos, colours) under `doc['_style']`.
    """

    name: str

    @abstractmethod
    def build(self, ctx: BuildContext) -> dict[str, Any]: ...

    def brand_style(self, brand: Brand) -> dict[str, Any]:
        return {"primary": brand.primary, "light": brand.light, "logo": brand.logo}
