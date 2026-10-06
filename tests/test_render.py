"""End-to-end tests that launch headless Chromium (slower)."""

import pytest

from reverse_docling.doctypes import doc_types, templates_for
from reverse_docling.manifest import read_manifest
from reverse_docling.models import GenerationRequest
from reverse_docling.pipeline import generate


@pytest.fixture(scope="module")
def every_template_pdf(tmp_path_factory):
    out = tmp_path_factory.mktemp("pdf")
    req = GenerationRequest(seed=1, documents=[{"type": t} for t in doc_types()], languages=["en", "ar", "ja"],
                            output={"format": "pdf", "dir": str(out)})
    return out, read_manifest(generate(req))


def test_every_template_renders_in_ltr_rtl_and_cjk(every_template_pdf):
    out, records = every_template_pdf
    expected = sum(len(templates_for(t)) for t in doc_types()) * 3
    assert len(records) == expected
    for rec in records:
        assert rec["pages"] >= 1
        pdf = out / rec["files"][0]
        assert pdf.read_bytes().startswith(b"%PDF")


def test_images_with_degradation_are_deterministic(tmp_path):
    def run(sub):
        req = GenerationRequest(seed=7, documents=[{"type": "invoice", "templates": ["t01_clean"]}], languages=["ru"],
                                output={"format": "images", "dir": str(tmp_path / sub), "dpi": 72},
                                degradation={"preset": "medium"})
        return read_manifest(generate(req))[0]

    a, b = run("a"), run("b")
    assert a["files"] == b["files"] and a["files"][0].endswith(".png")
    assert a["degradation"] == b["degradation"] and a["degradation"]
    assert (tmp_path / "a" / a["files"][0]).read_bytes() == (tmp_path / "b" / b["files"][0]).read_bytes()
