"""Orchestration: request -> jobs -> rendered, optionally degraded, files + manifest records."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .degrade import degrade_pages
from .doctypes import get_doc_type, templates_for
from .doctypes.base import BuildContext
from .i18n import Translator
from .identity import build_identity, identity_id
from .locales import get_language
from .manifest import ManifestWriter, to_jsonable
from .models import GenerationRequest, Identity, ManifestRecord
from .rasterize import encode_image, images_to_pdf, page_count, pdf_to_images
from .render import Renderer


@dataclass(frozen=True)
class Job:
    doc_type: str
    template: str
    language: str
    index: int

    @property
    def sample_id(self) -> str:
        return f"{self.doc_type}__{self.template}__{self.language}__{self.index:05d}"


def derive_seed(*parts: Any) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def expand_jobs(request: GenerationRequest) -> list[Job]:
    jobs = []
    for selection in request.documents:
        get_doc_type(selection.type)  # validate name early
        available = templates_for(selection.type)
        chosen = available if selection.templates == "all" else selection.templates
        missing = set(chosen) - set(available)
        if missing:
            raise ValueError(f"Unknown templates for {selection.type}: {sorted(missing)}. Available: {available}")
        for template in chosen:
            for lang in request.languages:
                for i in range(request.count_per_combination):
                    jobs.append(Job(selection.type, template, lang, i))
    return jobs


def identity_for(request: GenerationRequest, job: Job) -> Identity:
    lang = get_language(job.language)
    if request.identity.mode == "manual":
        # Same person across every document of a language; Faker fills only the gaps.
        return build_identity(request.identity, lang, derive_seed(request.seed, "identity", job.language))
    return build_identity(request.identity, lang, derive_seed(request.seed, "identity", job.sample_id))


def build_document(request: GenerationRequest, job: Job) -> tuple[Identity, dict[str, Any], random.Random]:
    rng = random.Random(derive_seed(request.seed, job.sample_id))
    lang = get_language(job.language)
    person = identity_for(request, job)
    doc = get_doc_type(job.doc_type).build(BuildContext(person, lang, Translator(lang.code), rng))
    return person, doc, rng


def render_job(renderer: Renderer, request: GenerationRequest, job: Job) -> tuple[bytes, Identity, dict[str, Any], random.Random]:
    person, doc, rng = build_document(request, job)
    lang = get_language(job.language)
    latin_digits = lang.code != "ar" or rng.random() < 0.6  # many Gulf documents use Western digits
    pdf = renderer.render_pdf(f"{job.doc_type}/{job.template}.html.j2", lang, {"doc": doc, "person": person},
                              latin_digits=latin_digits, specimen=request.specimen_watermark)
    return pdf, person, doc, rng


def run_job(renderer: Renderer, request: GenerationRequest, job: Job) -> ManifestRecord:
    pdf, person, doc, rng = render_job(renderer, request, job)
    out_dir = Path(request.output.dir)
    rel_dir = Path(job.doc_type) / job.language
    (out_dir / rel_dir).mkdir(parents=True, exist_ok=True)

    spec = request.degradation
    degrade = (spec.preset != "none" or spec.overrides) and rng.random() < spec.probability
    used_params = None
    files: list[str] = []

    if request.output.format == "pdf" and not degrade:
        rel = rel_dir / f"{job.sample_id}.pdf"
        (out_dir / rel).write_bytes(pdf)
        files.append(rel.as_posix())
        pages = page_count(pdf)
    else:
        images = pdf_to_images(pdf, request.output.dpi)
        if degrade:
            images, used_params = degrade_pages(images, spec.preset, rng, spec.overrides)
        pages = len(images)
        if request.output.format == "pdf":
            rel = rel_dir / f"{job.sample_id}.pdf"
            (out_dir / rel).write_bytes(images_to_pdf(images, request.output.dpi))
            files.append(rel.as_posix())
        else:
            page_dir = rel_dir / job.sample_id
            (out_dir / page_dir).mkdir(parents=True, exist_ok=True)
            ext = request.output.image_format
            for n, img in enumerate(images, start=1):
                rel = page_dir / f"page_{n:03d}.{ext}"
                (out_dir / rel).write_bytes(encode_image(img, ext))
                files.append(rel.as_posix())

    return ManifestRecord(
        id=job.sample_id, doc_type=job.doc_type, template=job.template, language=job.language,
        files=files, pages=pages, seed=request.seed, identity_id=identity_id(person),
        identity=to_jsonable(person.model_dump()), fields=to_jsonable(doc), degradation=used_params,
    )


def _run_chunk(request_json: str, jobs: list[Job]) -> list[dict[str, Any]]:
    request = GenerationRequest.model_validate_json(request_json)
    with Renderer() as renderer:
        return [run_job(renderer, request, job).model_dump() for job in jobs]


def _chunks(items: list[Job], n: int) -> Iterator[list[Job]]:
    size = max(1, min(25, len(items) // (n * 2) or 1))
    for i in range(0, len(items), size):
        yield items[i:i + size]


def generate(request: GenerationRequest, workers: int = 1,
             progress: Callable[[int, int], None] | None = None) -> Path:
    """Generate everything in `request`; returns the manifest path."""
    jobs = expand_jobs(request)
    out_dir = Path(request.output.dir)
    manifest_path = out_dir / "manifest.jsonl"
    done = 0
    with ManifestWriter(manifest_path) as manifest:
        if workers <= 1:
            with Renderer() as renderer:
                for job in jobs:
                    manifest.write(run_job(renderer, request, job))
                    done += 1
                    if progress:
                        progress(done, len(jobs))
        else:
            payload = request.model_dump_json()
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_run_chunk, payload, chunk) for chunk in _chunks(jobs, workers)]
                for future in as_completed(futures):
                    for record in future.result():
                        manifest.write(ManifestRecord(**record))
                        done += 1
                        if progress:
                            progress(done, len(jobs))
    return manifest_path
