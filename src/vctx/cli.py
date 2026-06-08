from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vctx.app.chunk import chunk_transcript_file
from vctx.app.config import WorkflowProfile
from vctx.app.doctor import doctor_report
from vctx.app.errors import VctxError
from vctx.app.metadata import inspect_metadata, render_metadata_text
from vctx.app.prepare import PrepareRequest, prepare_context_pack
from vctx.app.render import RenderFormat, render_from_files
from vctx.io.json_dump import model_to_json

app = typer.Typer(no_args_is_help=True)


@app.command("prepare")
def prepare_command(
    input: str,
    out: Annotated[Path, typer.Option("--out", help="Output directory for durable artifacts.")],
    language: Annotated[
        str | None, typer.Option("--language", help="Preferred subtitle language.")
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Allow writing into non-empty output directory.")
    ] = False,
    chunk_max_chars: Annotated[int, typer.Option("--chunk-max-chars")] = 6000,
    chunk_max_seconds: Annotated[int | None, typer.Option("--chunk-max-seconds")] = None,
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
    keep_temp: Annotated[bool, typer.Option("--keep-temp")] = False,
    workflow: Annotated[
        WorkflowProfile,
        typer.Option(
            "--workflow",
            help="Preparation workflow instance: default, transcript, visual, full, or metadata.",
        ),
    ] = WorkflowProfile.DEFAULT,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Use the offline workflow policy; network routes unavailable.",
        ),
    ] = False,
) -> None:
    try:
        result = prepare_context_pack(
            PrepareRequest(
                input=input,
                out_dir=out,
                language=language,
                overwrite=overwrite,
                chunk_max_chars=chunk_max_chars,
                chunk_max_seconds=chunk_max_seconds,
                cache_dir=cache_dir,
                keep_temp=keep_temp,
                workflow=workflow,
                offline=offline,
            )
        )
    except VctxError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc

    if result.manifest.status == "partial":
        typer.echo(f"Wrote partial context pack: {result.out_dir}")
    else:
        typer.echo(f"Wrote context pack: {result.out_dir}")
    typer.echo(f"Manifest: {result.out_dir / 'manifest.json'}")
    artifact_paths = {artifact.path for artifact in result.artifacts}
    if "metadata.json" in artifact_paths:
        typer.echo(f"Metadata: {result.out_dir / 'metadata.json'}")
    if "context.md" in artifact_paths:
        typer.echo(f"Context: {result.out_dir / 'context.md'}")
    if "readable.md" in artifact_paths:
        typer.echo(f"Readable: {result.out_dir / 'readable.md'}")


@app.command("metadata")
def metadata_command(
    input: str,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print normalized VideoMetadata JSON."),
    ] = False,
) -> None:
    try:
        metadata = inspect_metadata(input)
    except VctxError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc

    if json_output:
        typer.echo(model_to_json(metadata), nl=False)
    else:
        typer.echo(render_metadata_text(metadata), nl=False)


@app.command("chunk")
def chunk_command(
    transcript: Path,
    out: Annotated[Path, typer.Option("--out", help="Output chunks JSON file.")],
    chunk_max_chars: Annotated[int, typer.Option("--chunk-max-chars")] = 6000,
    chunk_max_seconds: Annotated[int | None, typer.Option("--chunk-max-seconds")] = None,
) -> None:
    try:
        chunks = chunk_transcript_file(
            transcript,
            max_chars=chunk_max_chars,
            max_seconds=chunk_max_seconds,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(model_to_json(chunks), encoding="utf-8")
    except VctxError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc
    except OSError as exc:
        typer.echo(f"error: failed to write chunks: {out}: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Wrote chunks: {out}")


@app.command("render")
def render_command(
    metadata: Annotated[Path, typer.Option("--metadata", help="Input metadata JSON file.")],
    transcript: Annotated[
        Path,
        typer.Option("--transcript", help="Input transcript JSON file."),
    ],
    out: Annotated[Path, typer.Option("--out", help="Output Markdown file.")],
    format: Annotated[RenderFormat, typer.Option("--format", help="Render format.")],
    chunks: Annotated[Path | None, typer.Option("--chunks", help="Input chunks JSON file.")] = None,
) -> None:
    try:
        content = render_from_files(
            metadata_path=metadata,
            transcript_path=transcript,
            chunks_path=chunks,
            format=format,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    except VctxError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc
    except OSError as exc:
        typer.echo(f"error: failed to write render: {out}: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Wrote render: {out}")


@app.command("doctor")
def doctor_command() -> None:
    typer.echo(doctor_report(), nl=False)


def main() -> None:
    app()
