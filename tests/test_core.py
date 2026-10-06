"""Fast tests that don't launch a browser."""

import random
import re

import numpy as np
import pytest

from reverse_docling.degrade import PRESETS, degrade_pages
from reverse_docling.doctypes import doc_types, templates_for
from reverse_docling.doctypes.base import BuildContext
from reverse_docling.i18n import Translator, flatten_keys, load_table
from reverse_docling.identity import _iban, build_identity
from reverse_docling.locales import LANGUAGES
from reverse_docling.manifest import to_jsonable
from reverse_docling.models import GenerationRequest, IdentitySpec
from reverse_docling.pipeline import Job, build_document, expand_jobs
from reverse_docling.render import TEMPLATES_DIR


@pytest.mark.parametrize("code", list(LANGUAGES))
def test_i18n_tables_have_every_english_key(code):
    assert flatten_keys(load_table("en")) - flatten_keys(load_table(code)) == set()


def test_templates_only_use_existing_keys():
    keys = flatten_keys(load_table("en"))
    used = set()
    for path in TEMPLATES_DIR.rglob("*.j2"):
        used |= set(re.findall(r"""\bt\(\s*['"]([\w.]+)['"]""", path.read_text()))
    assert used, "no t() calls found"
    assert used - keys == set()


def test_every_doctype_has_templates():
    for name in doc_types():
        assert templates_for(name), name


@pytest.mark.parametrize("code", list(LANGUAGES))
def test_random_identity_is_complete_and_deterministic(code):
    lang = LANGUAGES[code]
    a = build_identity(IdentitySpec(), lang, 123)
    b = build_identity(IdentitySpec(), lang, 123)
    assert a == b
    for field in ("full_name", "latin_name", "date_of_birth", "father_name", "mother_name", "email"):
        assert getattr(a, field), field
    assert a.latin_name.isascii()
    assert a.address.city and a.address.country


def test_manual_identity_values_win():
    spec = IdentitySpec(mode="manual", full_name="Ana Souza", date_of_birth="1985-01-02",
                        address={"city": "Recife"})
    person = build_identity(spec, LANGUAGES["ru"], 1)
    assert person.full_name == "Ana Souza"
    assert person.date_of_birth.isoformat() == "1985-01-02"
    assert person.address.city == "Recife"
    assert person.address.street  # filled by Faker


def test_iban_checksum_is_valid():
    for country in ("SA", "DE", "FR", "BR", "ES", "RU"):
        iban = _iban(country, random.Random(7))
        rearranged = iban[4:] + iban[:4]
        assert int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


@pytest.mark.parametrize("doc_type", list(doc_types()))
@pytest.mark.parametrize("code", ["en", "ar", "zh"])
def test_doctype_build_is_json_serialisable(doc_type, code):
    lang = LANGUAGES[code]
    person = build_identity(IdentitySpec(), lang, 5)
    doc = doc_types()[doc_type].build(BuildContext(person, lang, Translator(code), random.Random(5)))
    fields = to_jsonable(doc)
    assert "_style" not in fields
    import json
    json.dumps(fields, ensure_ascii=False)


def test_bank_statement_balances_add_up():
    req = GenerationRequest(seed=3, documents=[{"type": "bank_statement"}])
    _, doc, _ = build_document(req, Job("bank_statement", "t01_classic", "en", 0))
    expected = doc["opening_balance"] + doc["total_credit"] - doc["total_debit"]
    assert doc["closing_balance"] == pytest.approx(expected, abs=0.05)
    assert doc["transactions"][-1]["balance"] == pytest.approx(doc["closing_balance"], abs=0.01)


def test_expand_jobs_counts_combinations():
    req = GenerationRequest(documents=[{"type": "bank_statement"}, {"type": "invoice", "templates": ["t01_clean"]}],
                            languages=["en", "ar"], count_per_combination=3)
    n_bank = len(templates_for("bank_statement"))
    assert len(expand_jobs(req)) == (n_bank + 1) * 2 * 3


def test_unknown_template_or_language_is_rejected():
    with pytest.raises(ValueError):
        expand_jobs(GenerationRequest(documents=[{"type": "invoice", "templates": ["nope"]}]))
    with pytest.raises(ValueError):
        GenerationRequest(documents=[{"type": "invoice"}], languages=["xx"])


@pytest.mark.parametrize("preset", list(PRESETS))
def test_degradation_keeps_shape_and_dtype(preset):
    page = np.full((400, 300, 3), 255, np.uint8)
    page[100:120, 50:250] = 0
    out, params = degrade_pages([page], preset, random.Random(1))
    assert out[0].shape == page.shape and out[0].dtype == np.uint8
    assert isinstance(params[0], dict)
