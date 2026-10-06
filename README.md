# reverse-docling

[Docling](https://github.com/docling-project/docling) turns documents into Markdown for AI. **reverse-docling**
goes the other way: from a persona it renders realistic documents (bank statements, flight tickets, hotel
reservations, birth certificates, …) in many languages, as a PDF or page images, optionally degraded to look
like a bad scan. Every document comes with a labelled manifest record, so you can use the output directly to
train or evaluate a document classifier.

All institutions, names and numbers are synthetic.

## Quick start

```bash
uv sync
uv run playwright install chromium
uv run python scripts/fetch_fonts.py      # optional: bundled Noto fonts for reproducible output
uv run rdock generate -c configs/example.yaml -w 4
```

Output:

```
out/example/
  manifest.jsonl
  bank_statement/ar/bank_statement__t02_modern__ar__00001/page_001.png
  flight_ticket/zh/flight_ticket__t01_eticket__zh__00000.pdf
  ...
```

Web UI (form, live preview of page 1, zip download):

```bash
uv run rdock serve        # http://127.0.0.1:8000
```

## What you can configure

| Setting | Options |
|---|---|
| **Identity** | `mode: random` (new persona per document) or `mode: manual` (your fields; gaps filled per language) |
| **Documents** | `bank_statement` (3 templates), `flight_ticket`, `hotel_reservation`, `birth_certificate`, `utility_bill`, `payslip`, `invoice` (2 each). Choose `templates: all` or a list |
| **Languages** | `en ar zh ru pt es fr de ja hi` (Arabic is RTL; Arabic may use Arabic‑Indic or Western digits) |
| **Output** | `format: pdf` (one file per document) or `images` (one PNG/JPG per page), `dpi` |
| **Degradation** | `preset: none / light / medium / heavy`, `probability`, per-effect `overrides` |
| **Volume** | `count_per_combination` → total = doc types × templates × languages × count |

See [configs/example.yaml](configs/example.yaml) for an annotated config.

Degradation effects: rotation, perspective warp, gaussian/motion blur, noise, salt & pepper, brightness,
contrast, down/up-scaling, paper tint, edge shadow, fold lines, grayscale, binarization, JPEG artefacts.
If a PDF is degraded, it is rasterized, degraded and rebuilt as an image-only PDF, like a real scan.

## Manifest

One JSON object per document in `manifest.jsonl`:

```json
{"id": "invoice__t01_clean__ru__00000", "doc_type": "invoice", "template": "t01_clean", "language": "ru",
 "files": ["invoice/ru/invoice__t01_clean__ru__00000/page_001.png"], "pages": 1, "seed": 42,
 "identity_id": "73755f239959", "identity": {...}, "fields": {"invoice_number": "...", "total": 1716299.62, ...},
 "degradation": [{"rotation": -1.2, "gaussian_noise": 7.4, "jpeg_quality": 61}]}
```

`doc_type` is the class label; `fields` holds the ground-truth values that appear on the document (useful for
extraction tasks too). Generation is deterministic for a given `seed`.

## CLI

```bash
uv run rdock list-doctypes
uv run rdock list-languages
uv run rdock generate -c config.yaml [-o out/dir] [-w 4] [--dry-run]
uv run rdock preview bank_statement t02_modern --lang ar --html   # iterate on a template
uv run rdock serve --port 8000
```

## Extending

**Add a template.** Drop a new `templates/<doc_type>/tNN_name.html.j2` that extends `_base/base.html.j2`. It is
discovered automatically. Inside a template you have:

- `doc`: the doc type's data (`doc._style.logo`, `doc._style.primary` and `doc._style.light` for branding)
- `person`: the `Identity`
- `t('section.key', **params)`: translated label
- `fmt.date(d, 'short'|'medium'|'long'|'full'|pattern)`, `fmt.time(...)`, `fmt.money(x, symbol=True)`, `fmt.number(x)`

Use logical CSS (`text-align: start/end`, `margin-inline-start`) so RTL works automatically. Wrap
IDs/IBANs in `<span class="ltr">` inside RTL pages. Page setup goes in `{% block meta %}`:
`<meta name="rdock-paper" content="A4|Letter|A5-landscape|210mmx90mm">`,
`<meta name="rdock-footer" content="off">`, `<meta name="rdock-margin" content="10mm">`.

**Add a doc type.** Create `doctypes/<name>.py` with a `DocType` subclass whose `build(ctx)` returns a dict,
and export it as `DOC_TYPE = MyType()`. Add its labels to every `i18n/*.yaml`, then add templates.

**Add a language.** Register it in [locales.py](src/reverse_docling/locales.py) (Faker locale, Babel locale,
direction, currency, font stack) and add `i18n/<code>.yaml` with the same keys as `en.yaml`. Tests check that
every key is covered.

## Tests

```bash
uv run pytest
```

Tests cover i18n key coverage, identity generation per locale, IBAN checksums, balance arithmetic, degradation,
and end-to-end rendering of every template in LTR, RTL and CJK, plus determinism.
