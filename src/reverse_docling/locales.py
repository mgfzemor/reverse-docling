"""Language registry: everything a template needs to know about a language."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    faker_locale: str
    babel_locale: str
    direction: str  # "ltr" | "rtl"
    currency: str
    font_stack: str  # CSS font-family list; bundled Noto first, then OS fallbacks
    paper: str = "A4"  # "A4" | "Letter"


_LATIN = "'Noto Sans', 'Helvetica Neue', Arial, sans-serif"

LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("en", "English", "en_US", "en_US", "ltr", "USD", _LATIN, paper="Letter"),
        Language("ar", "Arabic", "ar_SA", "ar_SA", "rtl", "SAR",
                 "'Noto Naskh Arabic', 'Geeza Pro', 'Noto Sans', Arial, sans-serif"),
        Language("zh", "Chinese (Simplified)", "zh_CN", "zh_Hans_CN", "ltr", "CNY",
                 "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans', sans-serif"),
        Language("ru", "Russian", "ru_RU", "ru_RU", "ltr", "RUB", _LATIN),
        Language("pt", "Portuguese (Brazil)", "pt_BR", "pt_BR", "ltr", "BRL", _LATIN),
        Language("es", "Spanish", "es_ES", "es_ES", "ltr", "EUR", _LATIN),
        Language("fr", "French", "fr_FR", "fr_FR", "ltr", "EUR", _LATIN),
        Language("de", "German", "de_DE", "de_DE", "ltr", "EUR", _LATIN),
        Language("ja", "Japanese", "ja_JP", "ja_JP", "ltr", "JPY",
                 "'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', 'Noto Sans', sans-serif"),
        Language("hi", "Hindi", "hi_IN", "hi_IN", "ltr", "INR",
                 "'Noto Sans Devanagari', 'Kohinoor Devanagari', 'Noto Sans', sans-serif"),
    ]
}


def get_language(code: str) -> Language:
    try:
        return LANGUAGES[code]
    except KeyError:
        raise ValueError(f"Unknown language '{code}'. Available: {', '.join(LANGUAGES)}") from None
