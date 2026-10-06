"""Render Jinja2 HTML templates to PDF with headless Chromium (Playwright)."""

from __future__ import annotations

import datetime as dt
import re
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from babel.dates import format_date, format_datetime, format_time
from babel.numbers import format_currency, format_decimal, get_currency_symbol
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from playwright.sync_api import sync_playwright

from .i18n import Translator
from .locales import Language

TEMPLATES_DIR = Path(__file__).parent / "templates"
FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# family name -> font file stem prefix, used to emit @font-face only for fonts actually downloaded
_FONT_FILES = {
    "Noto Sans": "NotoSans[",
    "Noto Serif": "NotoSerif[",
    "Noto Sans Mono": "NotoSansMono[",
    "Noto Naskh Arabic": "NotoNaskhArabic[",
    "Noto Sans SC": "NotoSansSC[",
    "Noto Sans JP": "NotoSansJP[",
    "Noto Sans Devanagari": "NotoSansDevanagari[",
}


def font_face_css() -> str:
    if not FONTS_DIR.exists():
        return ""
    rules = []
    for family, prefix in _FONT_FILES.items():
        for f in sorted(FONTS_DIR.glob(f"{prefix}*.ttf")):
            rules.append(f"@font-face {{ font-family: '{family}'; src: url('{f.as_uri()}'); "
                         f"font-weight: 100 900; }}")
    return "\n".join(rules)


def make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


class Formatter:
    """Locale-aware formatting exposed to templates as `fmt`."""

    _NATIVE_DIGITS = {"ar": "arab", "hi": "deva"}

    def __init__(self, lang: Language, latin_digits: bool = True):
        self.lang = lang
        self.locale = lang.babel_locale
        self.numbering = "latn" if latin_digits else self._NATIVE_DIGITS.get(lang.code, "latn")
        self.rtl = lang.direction == "rtl"

    _DIGITS = {"arab": str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"),
               "deva": str.maketrans("0123456789", "०१२३४५६७८९")}

    def _isolate(self, s: str) -> str:
        """Apply native digits (Babel only swaps separators), and in RTL pages wrap numbers in LRI…PDI
        so the bidi algorithm can't reorder separators."""
        if self.numbering in self._DIGITS:
            s = s.translate(self._DIGITS[self.numbering])
        return f"⁦{s}⁩" if self.rtl else s

    def date(self, d: dt.date | None, style: str = "medium") -> str:
        if d is None:
            return ""
        if style == "iso":
            return d.isoformat()
        return format_date(d, format=style, locale=self.locale)

    def datetime(self, d: dt.datetime, style: str = "medium") -> str:
        return format_datetime(d, format=style, locale=self.locale)

    def time(self, d: dt.datetime | dt.time, style: str = "short") -> str:
        return format_time(d, format=style, locale=self.locale)

    def money(self, amount: float | Decimal, currency: str | None = None, symbol: bool = True) -> str:
        cur = currency or self.lang.currency
        if self.rtl:
            num = self._isolate(format_decimal(amount, format="#,##0.00", locale=self.locale,
                                               numbering_system=self.numbering))
            return f"{num}\xa0{get_currency_symbol(cur, locale=self.locale)}" if symbol else num
        if symbol:
            return self._isolate(format_currency(amount, cur, locale=self.locale, numbering_system=self.numbering))
        return self._isolate(format_decimal(amount, format="#,##0.00", locale=self.locale,
                                            numbering_system=self.numbering))

    def number(self, n: float, pattern: str | None = None) -> str:
        return self._isolate(format_decimal(n, format=pattern, locale=self.locale, numbering_system=self.numbering))


class Renderer:
    """Holds one Chromium instance; use as a context manager and call `render` many times."""

    def __init__(self) -> None:
        self.env = make_env()
        self._fonts_css = font_face_css()
        self._tmp = tempfile.TemporaryDirectory(prefix="rdock-")
        self._pw = self._browser = self._page = None

    def __enter__(self) -> "Renderer":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._tmp.cleanup()

    def render_html(self, template: str, lang: Language, context: dict[str, Any], latin_digits: bool = True,
                    specimen: bool = False) -> str:
        t = Translator(lang.code)
        ctx = dict(context, t=t, fmt=Formatter(lang, latin_digits), lang=lang, dir=lang.direction,
                   font_stack=lang.font_stack, fonts_css=self._fonts_css, specimen=specimen)
        return self.env.get_template(template).render(**ctx)

    def render_pdf(self, template: str, lang: Language, context: dict[str, Any], latin_digits: bool = True,
                   specimen: bool = False) -> bytes:
        html = self.render_html(template, lang, context, latin_digits, specimen)
        # Loading from a file:// URL (instead of set_content) lets @font-face reach local font files.
        path = Path(self._tmp.name) / "page.html"
        path.write_text(html, encoding="utf-8")
        assert self._page is not None, "Renderer must be used as a context manager"
        self._page.goto(path.as_uri(), wait_until="load")
        self._page.evaluate("document.fonts.ready")
        meta = _template_meta(html)
        opts: dict[str, Any] = dict(print_background=True, **_paper_options(meta.get("paper", lang.paper)))
        margin = meta.get("margin", "12mm")
        if meta.get("footer", "on") == "on":
            t = Translator(lang.code)
            opts.update(
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=(
                    f'<div dir="{lang.direction}" style="width:100%;font-size:7pt;color:#666;padding:0 12mm;'
                    f'font-family:{lang.font_stack};text-align:center">{t("common.page")} '
                    f'<span class="pageNumber"></span> / <span class="totalPages"></span></div>'),
                margin={"top": margin, "bottom": "14mm", "left": margin, "right": margin},
            )
        else:
            opts["margin"] = {side: margin for side in ("top", "bottom", "left", "right")}
        return self._page.pdf(**opts)


_META_RE = re.compile(r'<meta\s+name="rdock-([a-z]+)"\s+content="([^"]*)"')


def _template_meta(html: str) -> dict[str, str]:
    """Templates declare page setup with e.g. <meta name="rdock-paper" content="A5-landscape">."""
    return dict(_META_RE.findall(html[:4000]))


def _paper_options(paper: str) -> dict[str, Any]:
    """'A4', 'Letter', 'A5-landscape' or explicit '210mmx99mm'."""
    if "x" in paper and paper[0].isdigit():
        width, height = paper.split("x")
        return {"width": width, "height": height}
    name, _, orientation = paper.partition("-")
    return {"format": name, "landscape": orientation == "landscape"}
