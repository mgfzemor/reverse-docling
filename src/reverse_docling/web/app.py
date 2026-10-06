"""Small web UI: build a request in a form, preview a page, download a zip of the dataset."""

from __future__ import annotations

import base64
import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from ..degrade import PRESETS
from ..doctypes import doc_types, templates_for
from ..locales import LANGUAGES
from ..models import GenerationRequest
from ..pipeline import Job, expand_jobs, generate, render_job
from ..rasterize import encode_image, pdf_to_images
from ..render import Renderer

MAX_DOCUMENTS = 500  # keep synchronous web requests reasonable; use the CLI for big batches

app = FastAPI(title="reverse-docling")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    catalog = {name: templates_for(name) for name in doc_types()}
    return templates.TemplateResponse(request, "index.html", {
        "catalog": catalog, "languages": LANGUAGES, "presets": list(PRESETS),
    })


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    return {
        "doc_types": {name: templates_for(name) for name in doc_types()},
        "languages": {code: lang.name for code, lang in LANGUAGES.items()},
        "degradation_presets": list(PRESETS),
    }


def _parse(payload: dict[str, Any]) -> GenerationRequest:
    try:
        req = GenerationRequest.model_validate(payload)
        jobs = expand_jobs(req)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not jobs:
        raise HTTPException(status_code=422, detail="Nothing to generate: pick at least one document and language.")
    if len(jobs) > MAX_DOCUMENTS:
        raise HTTPException(status_code=422, detail=f"{len(jobs)} documents requested; the web UI allows "
                                                    f"{MAX_DOCUMENTS}. Use the CLI for larger batches.")
    return req


@app.post("/api/preview")
def preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Render the first combination's first page as a PNG (with degradation applied if enabled)."""
    req = _parse(payload)
    job: Job = expand_jobs(req)[0]
    with Renderer() as renderer:
        pdf, person, doc, rng = render_job(renderer, req, job)
    pages = pdf_to_images(pdf, 110)
    params = None
    if req.degradation.preset != "none" or req.degradation.overrides:
        from ..degrade import degrade_pages
        pages, params = degrade_pages(pages[:1], req.degradation.preset, rng, req.degradation.overrides)
    png = base64.b64encode(encode_image(pages[0], "png")).decode()
    return {"id": job.sample_id, "image": f"data:image/png;base64,{png}", "pages": len(pages),
            "identity": person.full_name, "degradation": params[0] if params else None,
            "total_documents": len(expand_jobs(req))}


@app.post("/api/generate")
def generate_zip(payload: dict[str, Any]) -> StreamingResponse:
    req = _parse(payload)
    with tempfile.TemporaryDirectory(prefix="rdock-web-") as tmp:
        req.output.dir = tmp
        generate(req)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(Path(tmp).rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(tmp).as_posix())
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": 'attachment; filename="reverse-docling.zip"'})
