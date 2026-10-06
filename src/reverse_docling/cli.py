"""Command-line interface: `rdock --help`."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from .doctypes import doc_types, templates_for
from .locales import LANGUAGES, get_language
from .models import GenerationRequest
from .pipeline import Job, expand_jobs, generate

app = typer.Typer(add_completion=False, help="Generate synthetic, labelled documents for classifier training.")


def load_request(path: Path) -> GenerationRequest:
    return GenerationRequest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@app.command("generate")
def generate_cmd(
    config: Path = typer.Option(..., "--config", "-c", exists=True, help="YAML generation request."),
    out: str | None = typer.Option(None, "--out", "-o", help="Override output.dir from the config."),
    workers: int = typer.Option(1, "--workers", "-w", min=1, help="Parallel Chromium processes."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only print how many documents would be generated."),
) -> None:
    """Generate every combination of doc type × template × language × count."""
    request = load_request(config)
    if out:
        request.output.dir = out
    jobs = expand_jobs(request)
    typer.echo(f"{len(jobs)} documents → {request.output.dir} ({request.output.format}, "
               f"degradation={request.degradation.preset})")
    if dry_run:
        return
    with typer.progressbar(length=len(jobs), label="Rendering") as bar:
        last = 0

        def progress(done: int, _total: int) -> None:
            nonlocal last
            bar.update(done - last)
            last = done

        manifest = generate(request, workers=workers, progress=progress)
    typer.echo(f"Manifest: {manifest}")


@app.command("list-doctypes")
def list_doctypes() -> None:
    """Show document types and their templates."""
    for name in doc_types():
        typer.echo(f"{name}: {', '.join(templates_for(name))}")


@app.command("list-languages")
def list_languages() -> None:
    """Show supported languages."""
    for code, lang in LANGUAGES.items():
        typer.echo(f"{code}  {lang.name:<22} {lang.direction}  {lang.currency}")


@app.command("preview")
def preview(
    doc_type: str = typer.Argument(..., help="Document type, e.g. bank_statement"),
    template: str = typer.Argument(..., help="Template id, e.g. t01_classic"),
    lang: str = typer.Option("en", "--lang", "-l"),
    seed: int = typer.Option(0, "--seed"),
    html: bool = typer.Option(False, "--html", help="Write the rendered HTML instead of a PDF."),
    out: Path = typer.Option(Path("preview"), "--out", "-o", help="Output path without extension."),
) -> None:
    """Render a single document, handy while authoring templates."""
    from .pipeline import build_document
    from .render import Renderer

    request = GenerationRequest(seed=seed, documents=[{"type": doc_type, "templates": [template]}], languages=[lang])
    job = Job(doc_type, template, lang, 0)
    person, doc, _ = build_document(request, job)
    with Renderer() as renderer:
        name = f"{doc_type}/{template}.html.j2"
        context = {"doc": doc, "person": person}
        if html:
            path = out.with_suffix(".html")
            path.write_text(renderer.render_html(name, get_language(lang), context), encoding="utf-8")
        else:
            path = out.with_suffix(".pdf")
            path.write_bytes(renderer.render_pdf(name, get_language(lang), context))
    typer.echo(f"Wrote {path}")


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the web UI."""
    import uvicorn

    uvicorn.run("reverse_docling.web.app:app", host=host, port=port)


if __name__ == "__main__":
    app()
