from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vctx.app.errors import VctxError
from vctx.app.prepare import PrepareRequest, prepare_context_pack

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
            )
        )
    except VctxError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc

    typer.echo(f"Wrote context pack: {result.out_dir}")
    typer.echo(f"Manifest: {result.out_dir / 'manifest.json'}")
    typer.echo(f"Context: {result.out_dir / 'context.md'}")
    typer.echo(f"Readable: {result.out_dir / 'readable.md'}")


@app.command("doctor")
def doctor_command() -> None:
    typer.echo("vctx doctor: ok")


def main() -> None:
    app()
